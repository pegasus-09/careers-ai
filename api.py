"""
FastAPI application for LaunchPad School Career Guidance System
Uses Supabase REST API (no pyroaring dependency)
"""
import os
from dotenv import load_dotenv

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

from datetime import datetime

load_dotenv()
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


class AddStudentRequest(BaseModel):
    email: str
    password: str
    full_name: str
    year_level: str


class AddTeacherRequest(BaseModel):
    email: str
    password: str
    full_name: str


class UpdateTeacherRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None


class UpdateStudentRequest(BaseModel):
    full_name: Optional[str] = None
    year_level: Optional[str] = None
    class_id: Optional[str] = None
    class_ids: Optional[List[str]] = None


class CreateClassRequest(BaseModel):
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_id: str
    year_level: str
    class_name: str
    student_ids: Optional[List[str]] = None


class UpdateClassRequest(BaseModel):
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_id: Optional[str] = None
    year_level: Optional[str] = None
    class_name: Optional[str] = None
    student_ids: Optional[List[str]] = None


HARD_CODED_SUBJECTS = [
    {"name": "English", "category": "Humanities"},
    {"name": "Maths", "category": "STEM"},
    {"name": "Physics", "category": "STEM"},
    {"name": "Chemistry", "category": "STEM"},
    {"name": "Biology", "category": "STEM"},
    {"name": "French", "category": "Languages"},
    {"name": "Latin", "category": "Languages"},
    {"name": "Japanese", "category": "Languages"},
    {"name": "German", "category": "Languages"},
    {"name": "Software Engineering", "category": "Vocational"},
    {"name": "Enterprise Computing", "category": "Vocational"},
    {"name": "Legal Studies", "category": "Humanities"},
    {"name": "Commerce", "category": "Humanities"},
    {"name": "Economics", "category": "Humanities"},
]


async def ensure_hardcoded_subjects(school_id: str):
    """Ensure fixed subject list exists for a school and return a name-indexed map."""
    seed_rows = [
        {
            "school_id": school_id,
            "name": subject["name"],
            "category": subject["category"]
        }
        for subject in HARD_CODED_SUBJECTS
    ]

    query = await supabase_client.query("subjects")
    insert_result = await query.upsert(seed_rows, on_conflict="school_id,name,category").execute()
    if insert_result.get("error"):
        raise Exception(insert_result["error"])

    query = await supabase_client.query("subjects")
    subjects_result = await query.select("id, name, category").eq("school_id", school_id).execute()

    existing_subjects = subjects_result["data"] or []
    existing_by_name = {}
    for subject in existing_subjects:
        name = subject.get("name")
        if name:
            existing_by_name[name.strip().lower()] = subject

    return existing_by_name

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "launchpad-backend",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# GUEST ENDPOINTS
# ============================================================================

@app.post("/guest/assessment", response_model=AssessmentResponse)
async def guest_assessment(submission: AssessmentSubmission):
    """Guest submits assessment answers and gets career rankings (no auth required)"""
    answers = submission.answers

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
        user_psychometrics = convert_answers_to_profile(answers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting answers: {str(e)}")

    # Rank careers using the profile
    try:
        _results, ranking = rank_profiles(user_psychometrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ranking careers: {str(e)}")

    profile_data = {"raw_scores": answers}

    return AssessmentResponse(
        ranking=ranking,
        profile_data=profile_data,
        message="Assessment completed successfully"
    )


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

        return {"students": profiles_result["data"]}
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
        # Get all students
        query = await supabase_client.query("profiles")
        students_result = await query.select("*").eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

        students = students_result["data"]

        if not students:
            return {"students": []}

        # Get all student IDs
        student_ids = [s["id"] for s in students]

        # Get all assessments for these students in one query
        query = await supabase_client.query("assessment_results")
        assessments_result = await query.select("user_id").in_("user_id", student_ids).execute()

        # Create set of student IDs who have assessments
        students_with_assessments = set(a["user_id"] for a in assessments_result["data"])

        # Get classes for students (multi-class)
        query = await supabase_client.query("student_classes")
        student_classes_result = await query.select("student_id, class_id").in_("student_id", student_ids).execute()

        class_ids_by_student = {}
        class_ids = []
        for sc in student_classes_result["data"]:
            class_ids_by_student.setdefault(sc["student_id"], []).append(sc["class_id"])
            class_ids.append(sc["class_id"])

        class_name_by_id = {}
        if class_ids:
            query = await supabase_client.query("classes")
            classes_result = await query.select("id, class_name").in_("id", list(set(class_ids))).execute()
            class_name_by_id = {c["id"]: c.get("class_name", "") for c in classes_result["data"]}

        # Get teacher comments (report availability)
        query = await supabase_client.query("teacher_comments")
        comments_result = await query.select("student_id").in_("student_id", student_ids).execute()
        students_with_teacher_comments = set(c["student_id"] for c in comments_result["data"])

        # Enrich student data
        enriched_students = []
        for student in students:
            student_class_ids = class_ids_by_student.get(student["id"], [])
            student_class_names = [class_name_by_id.get(class_id, "") for class_id in student_class_ids]
            enriched_students.append({
                "id": student["id"],
                "full_name": student["full_name"],
                "email": student["email"],
                "year_level": student.get("year_level", ""),
                "class_ids": student_class_ids,
                "class_names": student_class_names,
                "class_id": student_class_ids[0] if student_class_ids else None,
                "class_name": student_class_names[0] if student_class_names else "",
                "has_assessment": student["id"] in students_with_assessments,
                "has_teacher_comment": student["id"] in students_with_teacher_comments,
                "subjects_count": 0  # TODO: Add later
            })

        return {"students": enriched_students}
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

        # Get classes
        query = await supabase_client.query("student_classes")
        student_classes_result = await query.select("class_id").eq("student_id", student_id).execute()
        class_ids = [c["class_id"] for c in student_classes_result["data"]]

        classes = []
        subjects = []
        if class_ids:
            query = await supabase_client.query("classes")
            classes_result = await query.select("id, class_name, year_level, subject_id").in_("id", class_ids).execute()
            classes = classes_result["data"]

            subject_ids = list(set([c.get("subject_id") for c in classes if c.get("subject_id")]))
            if subject_ids:
                query = await supabase_client.query("subjects")
                subjects_result = await query.select("id, name, category").in_("id", subject_ids).execute()
                subjects = subjects_result["data"]

        class_name_by_id = {c["id"]: c.get("class_name", "") for c in classes}
        student["class_ids"] = class_ids
        student["class_names"] = [class_name_by_id.get(class_id, "") for class_id in class_ids]
        student["class_id"] = class_ids[0] if class_ids else None
        student["class_name"] = class_name_by_id.get(student["class_id"], "")

        # Get comments
        query = await supabase_client.query("teacher_comments")
        comments_result = await query.select("*").eq("student_id", student_id).execute()
        comments = comments_result["data"]

        teacher_ids = list(set([c.get("teacher_id") for c in comments if c.get("teacher_id")]))
        teacher_name_by_id = {}
        if teacher_ids:
            query = await supabase_client.query("profiles")
            teachers_result = await query.select("id, full_name").in_("id", teacher_ids).execute()
            teacher_name_by_id = {t["id"]: t.get("full_name", "") for t in teachers_result["data"]}

        for c in comments:
            c["teacher_name"] = teacher_name_by_id.get(c.get("teacher_id"))
            c["class_name"] = class_name_by_id.get(c.get("class_id"))

        return {
            "profile": student,
            "assessment": assessment_result["data"][0] if assessment_result["data"] else None,
            "classes": classes,
            "subjects": subjects,
            "comments": comments
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.put("/admin/student/{student_id}")
async def update_student(
        student_id: str,
        request: UpdateStudentRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin updates student profile (name/year/class)"""
    try:
        # Verify student exists and belongs to school
        query = await supabase_client.query("profiles")
        student_check = await query.select("*").eq("id", student_id).eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

        if not student_check["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        current_year_level = student_check["data"][0].get("year_level")
        effective_year_level = request.year_level if request.year_level is not None else current_year_level

        update_data = {}
        if request.full_name is not None:
            update_data["full_name"] = request.full_name
        if request.year_level is not None:
            update_data["year_level"] = request.year_level

        if update_data:
            query = await supabase_client.query("profiles")
            result = await query.update(update_data).eq("id", student_id).execute()
            if result.get("error"):
                raise Exception(result["error"])

        # Update class assignments (multi-class)
        if request.class_ids is not None:
            class_ids = [class_id for class_id in request.class_ids if class_id]
            unique_class_ids = list(dict.fromkeys(class_ids))

            if unique_class_ids:
                query = await supabase_client.query("classes")
                classes_result = await query.select("id, year_level").in_("id", unique_class_ids).eq(
                    "school_id", profile.school_id
                ).execute()

                classes = classes_result["data"]
                if len(classes) != len(unique_class_ids):
                    raise HTTPException(status_code=404, detail="One or more classes not found")

                mismatched = [
                    c for c in classes
                    if not c.get("year_level") or c.get("year_level") != effective_year_level
                ]
                if mismatched:
                    raise HTTPException(status_code=400,
                                        detail="All classes must match the student's year level")

            query = await supabase_client.query("student_classes")
            await query.delete().eq("student_id", student_id).execute()

            if unique_class_ids:
                insert_rows = [{"student_id": student_id, "class_id": class_id} for class_id in unique_class_ids]
                query = await supabase_client.query("student_classes")
                insert_result = await query.insert(insert_rows).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        # Backwards-compatible single class assignment
        elif request.class_id is not None:
            class_id = request.class_id or None
            if class_id:
                query = await supabase_client.query("classes")
                class_check = await query.select("id, year_level").eq("id", class_id).eq("school_id", profile.school_id).execute()
                if not class_check["data"]:
                    raise HTTPException(status_code=404, detail="Class not found")
                class_year_level = class_check["data"][0].get("year_level")
                if not class_year_level or class_year_level != effective_year_level:
                    raise HTTPException(status_code=400, detail="Class year level must match the student's year level")

            query = await supabase_client.query("student_classes")
            await query.delete().eq("student_id", student_id).execute()

            if class_id:
                insert_result = await query.insert({"student_id": student_id, "class_id": class_id}).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        # Validate existing assignments when only year level changes
        elif request.year_level is not None:
            query = await supabase_client.query("student_classes")
            student_classes_result = await query.select("class_id").eq("student_id", student_id).execute()
            existing_class_ids = [row["class_id"] for row in student_classes_result["data"]]

            if existing_class_ids:
                query = await supabase_client.query("classes")
                classes_result = await query.select("id, year_level").in_("id", existing_class_ids).execute()
                mismatched = [
                    c for c in classes_result["data"]
                    if not c.get("year_level") or c.get("year_level") != effective_year_level
                ]
                if mismatched:
                    raise HTTPException(status_code=400,
                                        detail="Existing classes do not match the new year level")

        return {"message": "Student updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/admin/student/{student_id}")
async def delete_student(
        student_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin deletes student (cascades to related records)"""
    try:
        # Verify student exists and belongs to school
        query = await supabase_client.query("profiles")
        student_check = await query.select("*").eq("id", student_id).eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

        if not student_check["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        # Delete profile (cascades due to foreign keys)
        query = await supabase_client.query("profiles")
        result = await query.delete().eq("id", student_id).execute()
        if result.get("error"):
            raise Exception(result["error"])

        # Delete from auth
        import httpx
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY")

        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{supabase_url}/auth/v1/admin/users/{student_id}",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                }
            )

        return {"message": "Student deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/admin/stats")
async def get_school_stats(
        profile: Profile = Depends(require_admin)
):
    """Get school-wide statistics"""
    try:
        school_id = profile.school_id

        # Count students
        query = await supabase_client.query("profiles")
        students_result = await query.select("id").eq("school_id", school_id).eq("role", UserRole.STUDENT).execute()
        total_students = len(students_result.get("data", []))

        # Count teachers
        query = await supabase_client.query("profiles")
        teachers_result = await query.select("id").eq("school_id", school_id).eq("role", UserRole.TEACHER).execute()
        total_teachers = len(teachers_result.get("data", []))

        # Count classes
        query = await supabase_client.query("classes")
        classes_result = await query.select("id").eq("school_id", school_id).execute()
        total_classes = len(classes_result.get("data", []))

        # Count assessments completed
        query = await supabase_client.query("assessment_results")
        assessments_result = await query.select("user_id").eq("school_id", school_id).execute()
        total_assessments = len(assessments_result.get("data", []))

        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "completed_assessments": total_assessments
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load stats: {str(e)}")


@app.post("/admin/add-student")
async def add_student(
        request: AddStudentRequest,  # ← Changed to use Pydantic model
        profile: Profile = Depends(require_admin)
):
    """Admin adds a new student to the school"""
    try:
        # Create auth user in Supabase
        import httpx

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY")

        # Create user via Supabase Admin API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{supabase_url}/auth/v1/admin/users",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "email": request.email,
                    "password": request.password,
                    "email_confirm": True
                }
            )

            if response.status_code != 200:
                error_detail = response.json()
                raise HTTPException(status_code=400, detail=f"Failed to create user: {error_detail}")

            user_data = response.json()
            user_id = user_data["id"]

        # Create profile
        profile_data = {
            "id": user_id,
            "school_id": profile.school_id,
            "role": UserRole.STUDENT,
            "full_name": request.full_name,
            "email": request.email,
            "year_level": request.year_level
        }

        query = await supabase_client.query("profiles")
        result = await query.insert(profile_data).execute()

        if result.get("error"):
            raise Exception(result["error"])

        return {
            "id": user_id,
            "message": "Student added successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN TEACHER ENDPOINTS
# ============================================================================

@app.get("/admin/teachers")
async def get_all_teachers(
        profile: Profile = Depends(require_admin)
):
    """Admin gets all teachers with their classes and subjects"""
    try:
        # Get all teachers
        query = await supabase_client.query("profiles")
        teachers_result = await query.select("*").eq("school_id", profile.school_id).eq("role",
                                                                                        UserRole.TEACHER).execute()

        teachers = teachers_result["data"]

        if not teachers:
            return {"teachers": []}

        enriched_teachers = []

        for teacher in teachers:
            teacher_id = teacher["id"]

            # Get classes taught by this teacher
            query = await supabase_client.query("classes")
            classes_result = await query.select("id, class_name, year_level, subject_id").eq("teacher_id",
                                                                                             teacher_id).execute()

            classes_taught = classes_result["data"]

            # Get unique subject IDs
            subject_ids = list(set([c["subject_id"] for c in classes_taught]))

            # Get subject details
            subjects_taught = []
            if subject_ids:
                query = await supabase_client.query("subjects")
                subjects_result = await query.select("id, name, category").in_("id", subject_ids).execute()
                subjects_taught = subjects_result["data"]

            enriched_teachers.append({
                "id": teacher["id"],
                "full_name": teacher["full_name"],
                "email": teacher["email"],
                "classes_taught": classes_taught,
                "subjects_taught": subjects_taught,
                "classes_count": len(classes_taught),
                "subjects_count": len(subjects_taught)
            })

        return {"teachers": enriched_teachers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/admin/teacher/{teacher_id}")
async def get_teacher_details(
        teacher_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin gets detailed teacher information"""
    try:
        # Get teacher profile
        query = await supabase_client.query("profiles")
        teacher_result = await query.select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
                                                                                                            UserRole.TEACHER).execute()

        if not teacher_result["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        teacher = teacher_result["data"][0]

        # Get classes taught
        query = await supabase_client.query("classes")
        classes_result = await query.select("*").eq("teacher_id", teacher_id).execute()

        classes = classes_result["data"]

        # Get subjects from classes
        subject_ids = list(set([c["subject_id"] for c in classes]))

        subjects = []
        if subject_ids:
            query = await supabase_client.query("subjects")
            subjects_result = await query.select("*").in_("id", subject_ids).execute()
            subjects = subjects_result["data"]

        # Get students in teacher's classes
        class_ids = [c["id"] for c in classes]

        students = []
        if class_ids:
            query = await supabase_client.query("student_classes")
            student_classes_result = await query.select("student_id, class_id").in_("class_id", class_ids).execute()

            student_ids = list(set([sc["student_id"] for sc in student_classes_result["data"]]))

            if student_ids:
                query = await supabase_client.query("profiles")
                students_result = await query.select("id, full_name, email, year_level").in_("id",
                                                                                             student_ids).execute()
                class_name_by_id = {c["id"]: c.get("class_name", "") for c in classes}
                class_ids_by_student = {}
                for sc in student_classes_result["data"]:
                    class_ids_by_student.setdefault(sc["student_id"], []).append(sc["class_id"])

                students = []
                for student in students_result["data"]:
                    student_class_ids = class_ids_by_student.get(student["id"], [])
                    student_class_names = [class_name_by_id.get(class_id, "") for class_id in student_class_ids]
                    enriched = {
                        **student,
                        "class_ids": student_class_ids,
                        "class_names": student_class_names,
                        "class_id": student_class_ids[0] if student_class_ids else None,
                        "class_name": student_class_names[0] if student_class_names else ""
                    }
                    students.append(enriched)

        return {
            "teacher": teacher,
            "classes": classes,
            "subjects": subjects,
            "students": students
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/admin/teacher")
async def add_teacher(
        request: AddTeacherRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin adds a new teacher to the school"""
    try:
        # Create auth user in Supabase
        import httpx

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY")

        # Create user via Supabase Admin API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{supabase_url}/auth/v1/admin/users",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "email": request.email,
                    "password": request.password,
                    "email_confirm": True
                }
            )

            if response.status_code != 200:
                error_detail = response.json()
                raise HTTPException(status_code=400, detail=f"Failed to create user: {error_detail}")

            user_data = response.json()
            user_id = user_data["id"]

        # Create profile
        profile_data = {
            "id": user_id,
            "school_id": profile.school_id,
            "role": UserRole.TEACHER,
            "full_name": request.full_name,
            "email": request.email
        }

        query = await supabase_client.query("profiles")
        result = await query.insert(profile_data).execute()

        if result.get("error"):
            raise Exception(result["error"])

        return {
            "id": user_id,
            "message": "Teacher added successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.put("/admin/teacher/{teacher_id}")
async def update_teacher(
        teacher_id: str,
        request: UpdateTeacherRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin updates teacher profile"""
    try:
        # Verify teacher exists and belongs to school
        query = await supabase_client.query("profiles")
        teacher_check = await query.select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
                                                                                                           UserRole.TEACHER).execute()

        if not teacher_check["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Build update data
        update_data = {}
        if request.full_name is not None:
            update_data["full_name"] = request.full_name
        if request.email is not None:
            update_data["email"] = request.email

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update profile
        query = await supabase_client.query("profiles")
        result = await query.update(update_data).eq("id", teacher_id).execute()

        if result.get("error"):
            raise Exception(result["error"])

        return {"message": "Teacher updated successfully", "teacher": result["data"][0]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/admin/teacher/{teacher_id}")
async def delete_teacher(
        teacher_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin deletes teacher (cascades to classes)"""
    try:
        # Verify teacher exists and belongs to school
        query = await supabase_client.query("profiles")
        teacher_check = await query.select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
                                                                                                           UserRole.TEACHER).execute()

        if not teacher_check["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Delete profile (cascades due to foreign keys)
        query = await supabase_client.query("profiles")
        result = await query.delete().eq("id", teacher_id).execute()

        if result.get("error"):
            raise Exception(result["error"])

        # Delete from auth
        import httpx
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY")

        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{supabase_url}/auth/v1/admin/users/{teacher_id}",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                }
            )

        return {"message": "Teacher deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN SUBJECT ENDPOINTS
# ============================================================================

@app.get("/admin/subjects")
async def get_all_subjects(
        profile: Profile = Depends(require_admin)
):
    """Admin gets all subjects in the school"""
    try:
        subjects_by_name = await ensure_hardcoded_subjects(profile.school_id)
        enriched_subjects = []

        for subject in HARD_CODED_SUBJECTS:
            key = subject["name"].strip().lower()
            existing = subjects_by_name.get(key)
            if not existing:
                continue

            # Count classes for this subject
            query = await supabase_client.query("classes")
            classes_result = await query.select("id").eq("subject_id", existing["id"]).execute()

            classes_count = len(classes_result["data"])

            enriched_subjects.append({
                "id": existing["id"],
                "name": existing.get("name", subject["name"]),
                "category": existing.get("category", subject["category"]),
                "year_level": existing.get("year_level", ""),
                "classes_count": classes_count
            })

        return {"subjects": enriched_subjects}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN CLASS ENDPOINTS
# ============================================================================

@app.get("/admin/classes")
async def get_all_classes(
        profile: Profile = Depends(require_admin)
):
    """Admin gets all classes in the school"""
    try:
        # Get all classes
        query = await supabase_client.query("classes")
        classes_result = await query.select("*").eq("school_id", profile.school_id).execute()

        classes = classes_result["data"]

        if not classes:
            return {"classes": []}

        enriched_classes = []

        for cls in classes:
            # Get subject
            query = await supabase_client.query("subjects")
            subject_result = await query.select("name, category").eq("id", cls["subject_id"]).execute()
            subject = subject_result["data"][0] if subject_result["data"] else {}

            # Get teacher
            query = await supabase_client.query("profiles")
            teacher_result = await query.select("full_name").eq("id", cls["teacher_id"]).execute()
            teacher = teacher_result["data"][0] if teacher_result["data"] else {}

            # Count students
            query = await supabase_client.query("student_classes")
            students_result = await query.select("student_id").eq("class_id", cls["id"]).execute()
            student_count = len(students_result["data"])

            enriched_classes.append({
                "id": cls["id"],
                "class_name": cls["class_name"],
                "year_level": cls["year_level"],
                "subject_name": subject.get("name", ""),
                "subject_category": subject.get("category", ""),
                "teacher_name": teacher.get("full_name", ""),
                "teacher_id": cls["teacher_id"],
                "subject_id": cls["subject_id"],
                "student_count": student_count
            })

        return {"classes": enriched_classes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/admin/class")
async def create_class(
        request: CreateClassRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin creates a new class"""
    try:
        subject_id = request.subject_id.strip() if request.subject_id else None
        subject_name = request.subject_name.strip() if request.subject_name else None
        if not subject_id and subject_name:
            subjects_by_name = await ensure_hardcoded_subjects(profile.school_id)
            subject = subjects_by_name.get(subject_name.lower())
            print(subject)
            if not subject:
                raise HTTPException(status_code=404, detail="Subject not found")
            subject_id = subject["id"]

        if not subject_id:
            raise HTTPException(status_code=400, detail="Subject is required")

        # Verify subject exists and belongs to school
        query = await supabase_client.query("subjects")
        subject_check = await query.select("*").eq("id", subject_id).eq("school_id",
                                                                                profile.school_id).execute()

        if not subject_check["data"]:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Verify teacher exists and belongs to school
        query = await supabase_client.query("profiles")
        teacher_check = await query.select("*").eq("id", request.teacher_id).eq("school_id", profile.school_id).eq(
            "role", UserRole.TEACHER).execute()

        if not teacher_check["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Create class
        class_data = {
            "school_id": profile.school_id,
            "subject_id": subject_id,
            "teacher_id": request.teacher_id,
            "year_level": request.year_level,
            "class_name": request.class_name
        }

        query = await supabase_client.query("classes")
        result = await query.insert(class_data).execute()

        if result.get("error"):
            raise Exception(result["error"])

        class_id = result["data"][0]["id"]

        # Assign students (optional)
        if request.student_ids is not None:
            student_ids = [student_id for student_id in request.student_ids if student_id]
            unique_student_ids = list(dict.fromkeys(student_ids))

            if unique_student_ids:
                query = await supabase_client.query("profiles")
                students_result = await query.select("id, year_level").in_("id", unique_student_ids).eq(
                    "school_id", profile.school_id
                ).eq("role", UserRole.STUDENT).execute()

                students = students_result["data"]
                if len(students) != len(unique_student_ids):
                    raise HTTPException(status_code=404, detail="One or more students not found")

                mismatched = [
                    s for s in students
                    if not s.get("year_level") or s.get("year_level") != request.year_level
                ]
                if mismatched:
                    raise HTTPException(status_code=400, detail="All students must be in the same year level as the class")

                insert_rows = [{"student_id": student_id, "class_id": class_id} for student_id in unique_student_ids]
                query = await supabase_client.query("student_classes")
                insert_result = await query.insert(insert_rows).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        return {
            "id": class_id,
            "message": "Class created successfully",
            "class": result["data"][0]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN CLASS UPDATE/DELETE ENDPOINTS
# ============================================================================

@app.put("/admin/class/{class_id}")
async def update_class(
        class_id: str,
        request: UpdateClassRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin updates class details and roster"""
    try:
        query = await supabase_client.query("classes")
        class_result = await query.select("*").eq("id", class_id).eq("school_id", profile.school_id).execute()

        if not class_result["data"]:
            raise HTTPException(status_code=404, detail="Class not found")

        existing_class = class_result["data"][0]

        subject_name = request.subject_name.strip() if request.subject_name else None
        if request.subject_id is not None or request.subject_name is not None:
            resolved_subject_id = request.subject_id.strip() if request.subject_id else None
            if resolved_subject_id is None and subject_name:
                subjects_by_name = await ensure_hardcoded_subjects(profile.school_id)
                subject = subjects_by_name.get(subject_name.lower())
                if not subject:
                    raise HTTPException(status_code=404, detail="Subject not found")
                resolved_subject_id = subject["id"]
            if resolved_subject_id:
                query = await supabase_client.query("subjects")
                subject_check = await query.select("id").eq("id", resolved_subject_id).eq("school_id",
                                                                                        profile.school_id).execute()
                if not subject_check["data"]:
                    raise HTTPException(status_code=404, detail="Subject not found")

        if request.teacher_id is not None:
            query = await supabase_client.query("profiles")
            teacher_check = await query.select("id").eq("id", request.teacher_id).eq("school_id",
                                                                                      profile.school_id).eq(
                "role", UserRole.TEACHER).execute()
            if not teacher_check["data"]:
                raise HTTPException(status_code=404, detail="Teacher not found")

        effective_year_level = request.year_level if request.year_level is not None else existing_class.get(
            "year_level"
        )

        if request.year_level is not None and request.student_ids is None:
            query = await supabase_client.query("student_classes")
            roster_result = await query.select("student_id").eq("class_id", class_id).execute()
            roster_ids = [row["student_id"] for row in roster_result["data"]]

            if roster_ids:
                query = await supabase_client.query("profiles")
                students_result = await query.select("id, year_level").in_("id", roster_ids).execute()
                mismatched = [
                    s for s in students_result["data"]
                    if not s.get("year_level") or s.get("year_level") != effective_year_level
                ]
                if mismatched:
                    raise HTTPException(status_code=400, detail="Existing students do not match the new year level")

        update_data = {}
        if request.subject_id is not None or request.subject_name is not None:
            if resolved_subject_id:
                update_data["subject_id"] = resolved_subject_id
        if request.teacher_id is not None:
            update_data["teacher_id"] = request.teacher_id
        if request.year_level is not None:
            update_data["year_level"] = request.year_level
        if request.class_name is not None:
            update_data["class_name"] = request.class_name

        if update_data:
            query = await supabase_client.query("classes")
            result = await query.update(update_data).eq("id", class_id).execute()
            if result.get("error"):
                raise Exception(result["error"])

        if request.student_ids is not None:
            student_ids = [student_id for student_id in request.student_ids if student_id]
            unique_student_ids = list(dict.fromkeys(student_ids))

            if unique_student_ids:
                query = await supabase_client.query("profiles")
                students_result = await query.select("id, year_level").in_("id", unique_student_ids).eq(
                    "school_id", profile.school_id
                ).eq("role", UserRole.STUDENT).execute()

                students = students_result["data"]
                if len(students) != len(unique_student_ids):
                    raise HTTPException(status_code=404, detail="One or more students not found")

                mismatched = [
                    s for s in students
                    if not s.get("year_level") or s.get("year_level") != effective_year_level
                ]
                if mismatched:
                    raise HTTPException(status_code=400,
                                        detail="All students must be in the same year level as the class")

            query = await supabase_client.query("student_classes")
            current_result = await query.select("student_id").eq("class_id", class_id).execute()
            current_ids = [row["student_id"] for row in current_result["data"]]

            current_set = set(current_ids)
            requested_set = set(unique_student_ids)

            to_add = [student_id for student_id in unique_student_ids if student_id not in current_set]
            to_remove = [student_id for student_id in current_ids if student_id not in requested_set]

            if to_remove:
                query = await supabase_client.query("student_classes")
                delete_result = await query.delete().eq("class_id", class_id).in_("student_id", to_remove).execute()
                if delete_result.get("error"):
                    raise Exception(delete_result["error"])

            if to_add:
                insert_rows = [{"student_id": student_id, "class_id": class_id} for student_id in to_add]
                query = await supabase_client.query("student_classes")
                insert_result = await query.insert(insert_rows).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        return {"message": "Class updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/admin/class/{class_id}")
async def delete_class(
        class_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin deletes a class and clears roster"""
    try:
        query = await supabase_client.query("classes")
        class_result = await query.select("id").eq("id", class_id).eq("school_id", profile.school_id).execute()

        if not class_result["data"]:
            raise HTTPException(status_code=404, detail="Class not found")

        query = await supabase_client.query("student_classes")
        roster_delete = await query.delete().eq("class_id", class_id).execute()
        if roster_delete.get("error"):
            raise Exception(roster_delete["error"])

        query = await supabase_client.query("classes")
        class_delete = await query.delete().eq("id", class_id).execute()
        if class_delete.get("error"):
            raise Exception(class_delete["error"])

        return {"message": "Class deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# ADMIN REPORTS ENDPOINT
# ============================================================================

@app.get("/admin/reports/summary")
async def get_reports_summary(
        profile: Profile = Depends(require_admin)
):
    """Get reports summary with top careers per student"""
    try:
        school_id = profile.school_id

        # Get all classes in school
        query = await supabase_client.query("classes")
        classes_result = await query.select("*").eq("school_id", school_id).execute()

        classes = classes_result["data"]

        # Get all students with assessments
        query = await supabase_client.query("assessment_results")
        assessments_result = await query.select("user_id, ranking").eq("school_id", school_id).execute()

        assessments_by_user = {a["user_id"]: a["ranking"] for a in assessments_result["data"]}

        # Get all students
        query = await supabase_client.query("profiles")
        students_result = await query.select("id, full_name, email, year_level").eq("school_id", school_id).eq("role",
                                                                                                               UserRole.STUDENT).execute()

        students = students_result["data"]

        # Enrich students with top career
        enriched_students = []
        for student in students:
            student_id = student["id"]
            ranking = assessments_by_user.get(student_id)

            top_career = None
            if ranking and len(ranking) > 0:
                # ranking is [[soc_code, career_name, score], ...]
                top_career = {
                    "soc_code": ranking[0][0],
                    "career_name": ranking[0][1],
                    "score": ranking[0][2]
                }

            enriched_students.append({
                "id": student_id,
                "full_name": student["full_name"],
                "email": student["email"],
                "year_level": student.get("year_level", ""),
                "top_career": top_career,
                "has_assessment": ranking is not None
            })

        # Enrich classes with student count
        enriched_classes = []
        for cls in classes:
            class_id = cls["id"]

            # Count students in class
            query = await supabase_client.query("student_classes")
            student_classes_result = await query.select("student_id").eq("class_id", class_id).execute()

            student_count = len(student_classes_result["data"])

            # Get subject name
            query = await supabase_client.query("subjects")
            subject_result = await query.select("name, category").eq("id", cls["subject_id"]).execute()

            subject = subject_result["data"][0] if subject_result["data"] else {}

            # Get teacher name
            query = await supabase_client.query("profiles")
            teacher_result = await query.select("full_name").eq("id", cls["teacher_id"]).execute()

            teacher = teacher_result["data"][0] if teacher_result["data"] else {}

            enriched_classes.append({
                "id": class_id,
                "class_name": cls["class_name"],
                "year_level": cls["year_level"],
                "subject_name": subject.get("name", ""),
                "subject_category": subject.get("category", ""),
                "teacher_name": teacher.get("full_name", ""),
                "student_count": student_count
            })

        return {
            "classes": enriched_classes,
            "students": enriched_students
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
