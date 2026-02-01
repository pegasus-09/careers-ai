"""
FastAPI application for LaunchPad School Career Guidance System
Uses Supabase REST API (no pyroaring dependency)
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from pydantic import BaseModel

# Internal imports
from auth import get_current_user, AuthUser
from authorization import require_admin, require_teacher, require_student, require_profile
from database import get_user_profile, upsert_assessment_result, Profile, UserRole
from supabase_client import supabase_client

# Import existing matching logic
from scripts.rank_all_careers import rank_profiles
from inference.answer_converter import convert_answers_to_profile

app = FastAPI(title="LaunchPad Career Guidance API", version="2.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AssessmentSubmission(BaseModel):
    """Assessment answers from frontend"""
    answers: Dict[str, int]


class AssessmentResponse(BaseModel):
    """Response after assessment submission"""
    ranking: List[List]
    profile_data: Dict
    message: str


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "LaunchPad Career Guidance API",
        "version": "2.0.0"
    }


# ============================================================================
# STUDENT ENDPOINTS
# ============================================================================

@app.post("/student/assessment", response_model=AssessmentResponse)
async def submit_assessment(
    submission: AssessmentSubmission,
    user: AuthUser = Depends(get_current_user)
):
    """Student submits assessment answers and gets career rankings"""
    import time
    start_time = time.time()
    print("hi this is a test")

    try:
        # Get user profile
        profile = await get_user_profile(user.user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Verify student role
        if profile.role != UserRole.STUDENT:
            raise HTTPException(status_code=403, detail="Student access required")

        answers = submission.answers
        print(f"[TIMING] Profile fetch: {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"[ERROR] Initial setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Setup error: {str(e)}")

    # Validate answers
    required_ids = (
        [f"A{i}" for i in range(1, 6)] +
        [f"I{i}" for i in range(1, 7)] +
        [f"T{i}" for i in range(1, 7)] +
        [f"V{i}" for i in range(1, 7)] +
        [f"W{i}" for i in range(1, 5)]
    )

    missing = [qid for qid in required_ids if qid not in answers]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required questions: {', '.join(missing)}"
        )

    # Convert answers to psychometric profile
    try:
        convert_start = time.time()
        user_psychometrics = convert_answers_to_profile(answers)
        print(f"[TIMING] Convert answers: {time.time() - convert_start:.2f}s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting answers: {str(e)}")

    # Rank careers using the profile
    try:
        rank_start = time.time()
        print("[TIMING] Starting rank_profiles...")
        _results, ranking = rank_profiles(user_psychometrics)
        print(f"[TIMING] Rank careers: {time.time() - rank_start:.2f}s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ranking careers: {str(e)}")

    # Store raw answers as profile data
    profile_data = {"raw_scores": answers}
    print("THIS IS A CHECK")

    # Save to database
    try:
        save_start = time.time()
        success = await upsert_assessment_result(
            user_id=profile.id,
            school_id=profile.school_id,
            raw_answers=answers,
            ranking=ranking,
            profile_data=profile_data,
            user_token=user.token  # Pass user's token for RLS
        )
        print(f"[TIMING] Database save: {time.time() - save_start:.2f}s")

        if not success:
            print("OOPS")
            raise HTTPException(status_code=500, detail="Failed to save assessment results")
    except Exception as e:
        print(f"Assessment save error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    print(f"[TIMING] Total time: {time.time() - start_time:.2f}s")

    return AssessmentResponse(
        ranking=ranking,
        profile_data=profile_data,
        message="Assessment completed successfully"
    )


@app.get("/student/profile")
async def get_student_profile_data(
    profile: Profile = Depends(require_student)
):
    """Get complete student profile"""
    try:
        # Get assessment
        query = await supabase_client.query("assessment_results")
        assessment_result = await query.select("*").eq("user_id", profile.id).execute()
        assessment = assessment_result["data"][0] if assessment_result["data"] else None

        # Get classes
        query = await supabase_client.query("student_classes")
        classes_result = await query.select("*").eq("student_id", profile.id).execute()

        # Get comments
        query = await supabase_client.query("teacher_comments")
        comments_result = await query.select("*").eq("student_id", profile.id).execute()

        # Get attributes
        query = await supabase_client.query("student_attributes")
        attributes_result = await query.select("*").eq("student_id", profile.id).execute()

        # Get experiences
        query = await supabase_client.query("work_experiences")
        experiences_result = await query.select("*").eq("student_id", profile.id).execute()

        # Get projects
        query = await supabase_client.query("projects")
        projects_result = await query.select("*").eq("student_id", profile.id).execute()

        return {
            "profile": {
                "id": profile.id,
                "full_name": profile.full_name,
                "email": profile.email,
                "year_level": profile.year_level
            },
            "assessment": assessment,
            "classes": classes_result["data"],
            "comments": comments_result["data"],
            "attributes": attributes_result["data"],
            "experiences": experiences_result["data"],
            "projects": projects_result["data"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


@app.post("/student/work-experience")
async def add_work_experience(
    title: str,
    organisation: str,
    start_date: str,
    description: Optional[str] = None,
    end_date: Optional[str] = None,
    profile: Profile = Depends(require_student)
):
    """Student adds work experience"""
    try:
        data = {
            "student_id": profile.id,
            "title": title,
            "organisation": organisation,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "added_by": profile.id
        }

        query = await supabase_client.query("work_experiences")
        result = await query.insert(data).execute()

        if result["error"]:
            raise Exception(result["error"])

        return {"id": result["data"][0]["id"], "message": "Work experience added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# TEACHER ENDPOINTS
# ============================================================================

@app.get("/teacher/students")
async def get_teacher_students(
    profile: Profile = Depends(require_teacher)
):
    """Get all students in teacher's classes"""
    try:
        # Get teacher's classes
        query = await supabase_client.query("classes")
        classes_result = await query.select("id").eq("teacher_id", profile.id).execute()

        class_ids = [c["id"] for c in classes_result["data"]]

        if not class_ids:
            return []

        # Get students in those classes
        query = await supabase_client.query("student_classes")
        students_result = await query.select("student_id").in_("class_id", class_ids).execute()

        student_ids = list(set([s["student_id"] for s in students_result["data"]]))

        # Get student profiles
        query = await supabase_client.query("profiles")
        profiles_result = await query.select("*").in_("id", student_ids).execute()

        return profiles_result["data"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/teacher/comment")
async def add_teacher_comment(
    student_id: str,
    class_id: str,
    comment_text: str,
    performance_rating: Optional[int] = None,
    engagement_rating: Optional[int] = None,
    profile: Profile = Depends(require_teacher)
):
    """Teacher adds comment for student"""
    try:
        # Verify teacher teaches this class
        query = await supabase_client.query("classes")
        class_check = await query.select("*").eq("id", class_id).eq("teacher_id", profile.id).execute()

        if not class_check["data"]:
            raise HTTPException(status_code=403, detail="You don't teach this class")

        # Insert comment
        data = {
            "student_id": student_id,
            "teacher_id": profile.id,
            "class_id": class_id,
            "comment_text": comment_text,
            "performance_rating": performance_rating,
            "engagement_rating": engagement_rating
        }

        query = await supabase_client.query("teacher_comments")
        result = await query.insert(data).execute()

        return {"id": result["data"][0]["id"], "message": "Comment added"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.get("/admin/students")
async def get_all_students(
    profile: Profile = Depends(require_admin)
):
    """Admin gets all students in school"""
    try:
        query = await supabase_client.query("profiles")
        result = await query.select("*").eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

        return result["data"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/admin/student/{student_id}")
async def get_student_details(
    student_id: str,
    profile: Profile = Depends(require_admin)
):
    """Admin gets detailed student information"""
    try:
        # Get student profile
        query = await supabase_client.query("profiles")
        student_result = await query.select("*").eq("id", student_id).eq("school_id", profile.school_id).execute()

        if not student_result["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        student = student_result["data"][0]

        # Get assessment
        query = await supabase_client.query("assessment_results")
        assessment_result = await query.select("*").eq("user_id", student_id).execute()

        return {
            "profile": student,
            "assessment": assessment_result["data"][0] if assessment_result["data"] else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)