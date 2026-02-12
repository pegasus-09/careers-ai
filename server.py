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

# AI analysis engine (single comprehensive prompt)
from ai.analysis_engine import run_analysis
from ai.follow_up_generator import generate_follow_up_questions
from ai.quality_check import check_assessment_quality

from datetime import datetime
import time
import csv
from pathlib import Path

load_dotenv()

# ============================================================================
# O*NET SOC TITLE CACHE (loaded once at startup)
# ============================================================================

def load_soc_title_mapping() -> list[tuple[str, str, str]]:
    """Load O*NET occupation data into a search index of (code, title, title_lower) tuples."""
    csv_path = Path(__file__).parent / "data" / "onet" / "csv" / "occupation_data.csv"
    entries: list[tuple[str, str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["O*NET-SOC Code"]
            title = row["Title"]
            entries.append((code, title, title.lower()))
    return entries

SOC_INDEX = load_soc_title_mapping()
SOC_CODES_SET = {code for code, _, _ in SOC_INDEX}
print(f"Loaded {len(SOC_INDEX)} O*NET occupations into search index")
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


class AddCommentRequest(BaseModel):
    student_id: str
    class_id: str
    comment_text: str
    performance_rating: Optional[int] = None
    engagement_rating: Optional[int] = None


class CommentResponse(BaseModel):
    id: str
    student_id: str
    teacher_id: str
    class_id: str
    comment_text: str
    performance_rating: Optional[int] = None
    engagement_rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# Teacher-specific models for student details
class ClassDetail(BaseModel):
    id: str
    class_name: str
    subject_name: str

class StudentDetailResponse(BaseModel):
    id: str
    full_name: str
    email: str
    year_level: str
    classes: List[ClassDetail]


class CareerAspirationRequest(BaseModel):
    soc_codes: List[str]


class PortfolioData(BaseModel):
    summary: Optional[str] = None
    year_level: Optional[str] = None
    subjects: Optional[List[Dict]] = []
    work_experience: Optional[List[Dict]] = []
    certifications: Optional[List[Dict]] = []
    volunteering: Optional[List[Dict]] = []
    extracurriculars: Optional[List[Dict]] = []
    skills: Optional[List[str]] = []


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

    insert_result = await supabase_client.query("subjects").upsert(seed_rows, on_conflict="school_id,name,category").execute()
    if insert_result.get("error"):
        raise Exception(insert_result["error"])

    subjects_result = await supabase_client.query("subjects").select("id, name, category").eq("school_id", school_id).execute()

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
        assessment_result = await supabase_client.query("assessment_results").select("*").eq("user_id", profile.id).execute()
        assessment = assessment_result["data"][0] if assessment_result["data"] else None

        # Get classes
        classes_result = await supabase_client.query("student_classes").select("*").eq("student_id", profile.id).execute()

        # Get comments
        comments_result = await supabase_client.query("teacher_comments").select("*").eq("student_id", profile.id).execute()

        # Get attributes
        attributes_result = await supabase_client.query("student_attributes").select("*").eq("student_id", profile.id).execute()

        # Get experiences
        experiences_result = await supabase_client.query("work_experiences").select("*").eq("student_id", profile.id).execute()

        # Get projects
        projects_result = await supabase_client.query("projects").select("*").eq("student_id", profile.id).execute()

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

        result = await supabase_client.query("work_experiences").insert(data).execute()

        if result["error"]:
            raise Exception(result["error"])

        return {"id": result["data"][0]["id"], "message": "Work experience added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/student/portfolio")
async def get_student_portfolio(profile: Profile = Depends(require_student)):
    """Get student portfolio and autofill data from system tables"""
    try:
        # Always fetch autofill data from system tables
        # 1. Year level from profile
        year_level = profile.year_level

        # 2. Subjects from student_classes -> classes -> subjects
        classes_result = (
            await supabase_client.query("student_classes")
            .select("class_id")
            .eq("student_id", profile.id)
            .execute()
        )
        class_ids = [c["class_id"] for c in classes_result.get("data", [])]

        subjects = []
        if class_ids:
            classes_info = (
                await supabase_client.query("classes")
                .select("subject_id,class_name")
                .in_("id", class_ids)
                .execute()
            )
            subject_ids = list(set(
                c["subject_id"] for c in classes_info.get("data", []) if c.get("subject_id")
            ))
            if subject_ids:
                subjects_result = (
                    await supabase_client.query("subjects")
                    .select("id,name,category")
                    .in_("id", subject_ids)
                    .execute()
                )
                subjects = [
                    {"name": s["name"], "category": s.get("category", "")}
                    for s in subjects_result.get("data", [])
                ]

        # 3. Work experiences
        experiences_result = (
            await supabase_client.query("work_experiences")
            .select("title,organisation,description,start_date,end_date")
            .eq("student_id", profile.id)
            .execute()
        )
        work_experience = experiences_result.get("data", [])

        autofill = {
            "year_level": year_level,
            "subjects": subjects,
            "work_experience": work_experience,
        }

        # Fetch saved portfolio if exists
        portfolio_result = (
            await supabase_client.query("student_portfolios")
            .select("*")
            .eq("student_id", profile.id)
            .execute()
        )
        portfolio = portfolio_result["data"][0] if portfolio_result.get("data") else None

        return {"portfolio": portfolio, "autofill": autofill}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio: {str(e)}")


@app.put("/student/portfolio")
async def save_student_portfolio(
    request: PortfolioData,
    profile: Profile = Depends(require_student)
):
    """Save or update student portfolio"""
    try:
        portfolio_data = {
            "student_id": profile.id,
            "summary": request.summary,
            "year_level": request.year_level,
            "subjects": request.subjects,
            "work_experience": request.work_experience,
            "certifications": request.certifications,
            "volunteering": request.volunteering,
            "extracurriculars": request.extracurriculars,
            "skills": request.skills,
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Check if portfolio exists
        existing = (
            await supabase_client.query("student_portfolios")
            .select("student_id")
            .eq("student_id", profile.id)
            .execute()
        )

        if existing.get("data"):
            # Update existing
            update_data = {k: v for k, v in portfolio_data.items() if k != "student_id"}
            result = (
                await supabase_client.query("student_portfolios")
                .update(update_data)
                .eq("student_id", profile.id)
                .execute()
            )
            message = "Portfolio updated successfully"
        else:
            # Insert new
            result = (
                await supabase_client.query("student_portfolios")
                .insert(portfolio_data)
                .execute()
            )
            message = "Portfolio created successfully"

        if result.get("error"):
            raise Exception(result["error"])

        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving portfolio: {str(e)}")


# ============================================================================
# CAREER SEARCH & ASPIRATION ENDPOINTS
# ============================================================================


@app.get("/careers/search")
async def search_careers(
    q: str = "",
    profile: Profile = Depends(require_profile)
):
    """Search O*NET careers by title substring (case-insensitive). Max 10 results."""
    query = q.strip().lower()
    if not query or len(query) < 2:
        return {"results": []}

    results = []
    for code, title, title_lower in SOC_INDEX:
        if query in title_lower:
            results.append({"soc_code": code, "title": title})
            if len(results) >= 10:
                break

    return {"results": results}


@app.get("/student/career-aspirations")
async def get_student_career_aspirations(
    profile: Profile = Depends(require_student)
):
    """Student reads their saved career aspirations."""
    try:
        result = await supabase_client.query("student_career_aspirations") \
            .select("id, soc_code, title, created_at") \
            .eq("student_id", profile.id) \
            .execute()
        return {"aspirations": result.get("data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.put("/student/career-aspirations")
async def save_student_career_aspirations(
    request: CareerAspirationRequest,
    profile: Profile = Depends(require_student)
):
    """Replace the student's full career aspirations list."""
    try:
        # Validate SOC codes against in-memory cache
        invalid_codes = [c for c in request.soc_codes if c not in SOC_CODES_SET]
        if invalid_codes:
            raise HTTPException(status_code=400, detail=f"Invalid SOC codes: {', '.join(invalid_codes)}")

        # Delete existing aspirations
        await supabase_client.query("student_career_aspirations") \
            .delete() \
            .eq("student_id", profile.id) \
            .execute()

        # Insert new ones
        if request.soc_codes:
            # Build title lookup
            title_by_code = {code: title for code, title, _ in SOC_INDEX}
            rows = [
                {
                    "student_id": profile.id,
                    "soc_code": code,
                    "title": title_by_code[code],
                }
                for code in request.soc_codes
            ]
            result = await supabase_client.query("student_career_aspirations") \
                .insert(rows) \
                .execute()
            if result.get("error"):
                raise Exception(result["error"])

        return {"message": "Career aspirations saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# TEACHER ENDPOINTS
# ============================================================================


@app.get("/teacher/students")
async def get_teacher_students(profile: Profile = Depends(require_teacher)):
    """Teacher gets all students they teach"""
    try:
        # Get classes for this teacher
        classes_result = (
            await supabase_client.query("classes")
            .select("id")
            .eq("teacher_id", profile.id)
            .execute()
        )

        class_ids = [c["id"] for c in classes_result["data"]]

        if not class_ids:
            return {"students": []}

        # Get students in those classes
        students_result = (
            await supabase_client.query("student_classes")
            .select("student_id")
            .in_("class_id", class_ids)
            .execute()
        )

        student_ids = list(set([s["student_id"] for s in students_result["data"]]))

        if not student_ids:
            return {"students": []}

        # Get student profiles
        profiles_result = (
            await supabase_client.query("profiles")
            .select("*")
            .in_("id", student_ids)
            .execute()
        )

        # Enrich students with their class names
        students_with_classes = []
        for student in profiles_result["data"]:
            # Get class_ids this student is in
            student_class_ids_result = (
                await supabase_client.query("student_classes")
                .select("class_id")
                .eq("student_id", student["id"])
                .in_("class_id", class_ids)
                .execute()
            )
            student_class_ids_list = [sc["class_id"] for sc in student_class_ids_result["data"]]

            # Get class names with subjects
            if student_class_ids_list:
                classes_info_result = (
                    await supabase_client.query("classes")
                    .select("id, class_name, subject_id")
                    .in_("id", student_class_ids_list)
                    .execute()
                )
                class_names = []
                class_ids_for_student = []
                for c in classes_info_result["data"]:
                    class_names.append(c["class_name"])
                    class_ids_for_student.append(c["id"])
                student["class_names"] = class_names
                student["class_ids"] = class_ids_for_student
            else:
                student["class_names"] = []
                student["class_ids"] = []

            students_with_classes.append(student)

        return {"students": students_with_classes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/teacher/classes")
async def get_teacher_classes(profile: Profile = Depends(require_teacher)):
    """Teacher gets all classes they teach"""
    try:
        classes_result = (
            await supabase_client.query("classes")
            .select("id, class_name, subject_id, year_level")
            .eq("teacher_id", profile.id)
            .execute()
        )

        # Get subject names for each class
        classes_with_subjects = []
        for cls in classes_result["data"]:
            subject_result = (
                await supabase_client.query("subjects")
                .select("name")
                .eq("id", cls["subject_id"])
                .execute()
            )
            cls["subject_name"] = subject_result["data"][0]["name"] if subject_result["data"] else None
            classes_with_subjects.append(cls)

        return {"classes": classes_with_subjects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/teacher/student/{student_id}", response_model=StudentDetailResponse)
async def get_teacher_student_detail(
    student_id: str,
    profile: Profile = Depends(require_teacher)
):
    """Teacher gets detailed student information for a student assigned to their class."""
    print(f"\n[DEBUG] Teacher {profile.id} trying to access student {student_id}")
    try:
        # Verify student exists and belongs to the same school
        print("[DEBUG] 1. Fetching student profile...")
        student_profile_result = await supabase_client.query("profiles").select("*") \
            .eq("id", student_id) \
            .eq("school_id", profile.school_id) \
            .execute()
        print(f"[DEBUG]    ... Student profile result: {student_profile_result}")

        if not student_profile_result.get("data"):
            print("[DEBUG]    ... Student not found in school. Raising 404.")
            raise HTTPException(status_code=404, detail="Student not found or not in your school.")

        student_profile = student_profile_result["data"][0]
        print(f"[DEBUG]    ... Found student: {student_profile.get('full_name')}")


        if student_profile.get("role") != UserRole.STUDENT:
            print(f"[DEBUG]    ... User {student_id} is not a student. Raising 400.")
            raise HTTPException(status_code=400, detail="Provided ID does not belong to a student.")

        # Get classes that the student is part of AND that are taught by the current teacher
        # This is a bit complex as we need to join across student_classes, classes, and subjects

        # 1. Get all class_ids the student is enrolled in
        print("[DEBUG] 2. Fetching student's class enrollments...")
        student_classes_response = await supabase_client.query("student_classes").select("class_id") \
            .eq("student_id", student_id) \
            .execute()
        student_class_ids = [cls["class_id"] for cls in student_classes_response["data"]]
        print(f"[DEBUG]    ... Student is in class IDs: {student_class_ids}")


        if not student_class_ids:
            # Student is not in any classes, so definitely not in current teacher's classes.
            # This is not a 404 for the student, but a 403 for the teacher trying to access.
            print("[DEBUG]    ... Student is not in any classes. Raising 403.")
            raise HTTPException(status_code=403, detail="Student is not assigned to any of your classes.")

        # 2. Get details for these classes, filtering by the current teacher and joining with subjects
        print(f"[DEBUG] 3. Checking which of these classes are taught by teacher {profile.id}...")
        teacher_student_classes_result = await supabase_client.query("classes") \
            .select("id, class_name, subjects(name)") \
            .in_("id", student_class_ids) \
            .eq("teacher_id", profile.id) \
            .execute()

        teacher_student_classes_data = teacher_student_classes_result["data"]
        print(f"[DEBUG]    ... Teacher's classes for this student: {teacher_student_classes_data}")


        if not teacher_student_classes_data:
            print(f"[DEBUG]    ... Teacher does not teach any of the student's classes. Raising 403.")
            raise HTTPException(status_code=403, detail="Student is not assigned to any of your classes.")

        # Format classes for the response model
        formatted_classes: List[ClassDetail] = []
        for cls in teacher_student_classes_data:
            formatted_classes.append(ClassDetail(
                id=cls["id"],
                class_name=cls["class_name"],
                subject_name=cls["subjects"]["name"]  # Access nested subject name
            ))

        print("[DEBUG] 4. Successfully found student and classes. Returning data.")
        return StudentDetailResponse(
            id=student_profile["id"],
            full_name=student_profile["full_name"],
            email=student_profile["email"],
            year_level=student_profile["year_level"],
            classes=formatted_classes
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] An unexpected error occurred: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching student details: {str(e)}")


@app.post("/teacher/comment")
async def add_teacher_comment(
        request: AddCommentRequest,
        profile: Profile = Depends(require_teacher)
):
    """Teacher adds or updates a comment for a student in a specific class."""
    try:
        # Verify teacher teaches this class
        class_check = await supabase_client.query("classes").select("id").eq("id", request.class_id).eq("teacher_id", profile.id).execute()
        if not class_check.get("data"):
            raise HTTPException(status_code=403, detail="You do not teach this class.")

        # Check for existing comment
        existing_comment_result = await supabase_client.query("teacher_comments").select("id") \
            .eq("teacher_id", profile.id) \
            .eq("student_id", request.student_id) \
            .eq("class_id", request.class_id) \
            .execute()

        comment_data = {
            "student_id": request.student_id,
            "teacher_id": profile.id,
            "class_id": request.class_id,
            "comment_text": request.comment_text,
            "performance_rating": request.performance_rating,
            "engagement_rating": request.engagement_rating,
            "updated_at": datetime.utcnow().isoformat()
        }

        if existing_comment_result.get("data"):
            # UPDATE existing comment
            comment_id = existing_comment_result["data"][0]["id"]
            result = await supabase_client.query("teacher_comments").update(comment_data).eq("id", comment_id).execute()
            message = "Comment updated successfully"
        else:
            # INSERT new comment
            result = await supabase_client.query("teacher_comments").insert(comment_data).execute()
            message = "Comment added successfully"

        if not result.get("data"):
             raise HTTPException(status_code=500, detail="Failed to save comment")

        return {"id": result["data"][0]["id"], "message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving comment: {str(e)}")


@app.get("/teacher/student/{student_id}/class/{class_id}/comment", response_model=Optional[CommentResponse])
async def get_teacher_comment(
    student_id: str,
    class_id: str,
    profile: Profile = Depends(require_teacher)
):
    """Teacher gets their comment for a student in a specific class."""
    try:
        comment_result = await supabase_client.query("teacher_comments").select("*") \
            .eq("teacher_id", profile.id) \
            .eq("student_id", student_id) \
            .eq("class_id", class_id) \
            .execute()

        if comment_result.get("data"):
            return comment_result["data"][0]
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching comment: {str(e)}")


@app.delete("/teacher/student/{student_id}/class/{class_id}/comment")
async def delete_teacher_comment(
    student_id: str,
    class_id: str,
    profile: Profile = Depends(require_teacher)
):
    """Teacher deletes their comment for a student in a specific class."""
    try:
        # First, find the comment to ensure it belongs to the teacher
        comment_result = await supabase_client.query("teacher_comments").select("id") \
            .eq("teacher_id", profile.id) \
            .eq("student_id", student_id) \
            .eq("class_id", class_id) \
            .execute()

        if not comment_result.get("data"):
            raise HTTPException(status_code=404, detail="Comment not found.")

        comment_id = comment_result["data"][0]["id"]

        delete_result = await supabase_client.query("teacher_comments").delete().eq("id", comment_id).execute()

        # The delete operation in this client might not return data on success,
        # so check for error instead of data.
        if delete_result.get("error"):
            raise HTTPException(status_code=500, detail=f"Failed to delete comment: {delete_result['error']}")

        return {"message": "Comment deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting comment: {str(e)}")


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.get("/admin/students")
async def get_all_students(
        profile: Profile = Depends(require_admin)
):
    """Admin gets all students in school"""
    start_time = time.time()
    try:
        # 1. Get all students for the school
        students_result = await supabase_client.query("profiles") \
            .select("id, full_name, email, year_level") \
            .eq("school_id", profile.school_id) \
            .eq("role", UserRole.STUDENT) \
            .execute()

        students = students_result.get("data", [])
        if not students:
            return {"students": []}

        student_ids = [s["id"] for s in students]

        # 2. Get all related data in batches
        assessments_result = await supabase_client.query("assessment_results").select("user_id").in_("user_id", student_ids).execute()
        student_classes_result = await supabase_client.query("student_classes").select("student_id, class_id").in_("student_id", student_ids).execute()
        comments_result = await supabase_client.query("teacher_comments").select("student_id").in_("student_id", student_ids).execute()

        # 3. Process into lookup maps
        students_with_assessments = {a["user_id"] for a in assessments_result.get("data", [])}
        students_with_teacher_comments = {c["student_id"] for c in comments_result.get("data", [])}

        class_ids_by_student = {}
        all_class_ids = set()
        for sc in student_classes_result.get("data", []):
            class_ids_by_student.setdefault(sc["student_id"], []).append(sc["class_id"])
            all_class_ids.add(sc["class_id"])

        class_name_by_id = {}
        if all_class_ids:
            classes_result = await supabase_client.query("classes").select("id, class_name").in_("id", list(all_class_ids)).execute()
            class_name_by_id = {c["id"]: c.get("class_name", "") for c in classes_result.get("data", [])}

        # 4. Enrich student data
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
                "has_assessment": student["id"] in students_with_assessments,
                "has_teacher_comment": student["id"] in students_with_teacher_comments,
            })

        return {"students": enriched_students}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        end_time = time.time()
        print(f"PERF: get_all_students took {end_time - start_time:.4f} seconds.")


@app.get("/admin/student/{student_id}")
async def get_student_details(
        student_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin gets detailed student information"""
    try:
        # Get student profile
        student_result = await supabase_client.query("profiles").select("*").eq("id", student_id).eq("school_id", profile.school_id).execute()

        if not student_result["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        student = student_result["data"][0]

        # Get assessment
        assessment_result = await supabase_client.query("assessment_results").select("*").eq("user_id", student_id).execute()

        # Get classes
        student_classes_result = await supabase_client.query("student_classes").select("class_id").eq("student_id", student_id).execute()
        class_ids = [c["class_id"] for c in student_classes_result["data"]]

        classes = []
        subjects = []
        if class_ids:
            classes_result = await supabase_client.query("classes").select("id, class_name, year_level, subject_id").in_("id", class_ids).execute()
            classes = classes_result["data"]

            subject_ids = list(set([c.get("subject_id") for c in classes if c.get("subject_id")]))
            if subject_ids:
                subjects_result = await supabase_client.query("subjects").select("id, name, category").in_("id", subject_ids).execute()
                subjects = subjects_result["data"]

        class_name_by_id = {c["id"]: c.get("class_name", "") for c in classes}
        student["class_ids"] = class_ids
        student["class_names"] = [class_name_by_id.get(class_id, "") for class_id in class_ids]
        student["class_id"] = class_ids[0] if class_ids else None
        student["class_name"] = class_name_by_id.get(student["class_id"], "")

        # Get comments
        comments_result = await supabase_client.query("teacher_comments").select("*").eq("student_id", student_id).execute()
        comments = comments_result["data"]

        teacher_ids = list(set([c.get("teacher_id") for c in comments if c.get("teacher_id")]))
        teacher_name_by_id = {}
        if teacher_ids:
            teachers_result = await supabase_client.query("profiles").select("id, full_name").in_("id", teacher_ids).execute()
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


@app.get("/admin/student/{student_id}/career-aspirations")
async def get_student_career_aspirations_admin(
    student_id: str,
    profile: Profile = Depends(require_admin)
):
    """Admin reads a student's career aspirations (with school_id check)."""
    try:
        # Verify student belongs to same school
        student_check = await supabase_client.query("profiles").select("id").eq("id", student_id).eq("school_id", profile.school_id).execute()
        if not student_check["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        result = await supabase_client.query("student_career_aspirations") \
            .select("id, soc_code, title, created_at") \
            .eq("student_id", student_id) \
            .execute()
        return {"aspirations": result.get("data", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/admin/student/{student_id}/portfolio")
async def get_student_portfolio_admin(
        student_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin gets a student's saved portfolio"""
    try:
        # Verify student belongs to same school
        student_result = await supabase_client.query("profiles").select("id,full_name,year_level,school_id").eq("id", student_id).eq("school_id", profile.school_id).execute()
        if not student_result["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        student = student_result["data"][0]

        portfolio_result = await supabase_client.query("student_portfolios").select("*").eq("student_id", student_id).execute()
        portfolio = portfolio_result["data"][0] if portfolio_result.get("data") else None

        return {"portfolio": portfolio, "student_name": student.get("full_name", ""), "year_level": student.get("year_level", "")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/admin/student/{student_id}/notes")
async def get_student_notes(
        student_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin gets all notes for a student"""
    try:
        notes_result = await supabase_client.query("admin_notes") \
            .select("*") \
            .eq("student_id", student_id) \
            .eq("school_id", profile.school_id) \
            .execute()
        return {"notes": notes_result.get("data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


class AdminNoteRequest(BaseModel):
    note_text: str


@app.post("/admin/student/{student_id}/note")
async def add_student_note(
        student_id: str,
        request: AdminNoteRequest,
        profile: Profile = Depends(require_admin)
):
    """Admin adds a note on a student"""
    try:
        # Verify student belongs to same school
        student_check = await supabase_client.query("profiles").select("id").eq("id", student_id).eq("school_id", profile.school_id).execute()
        if not student_check["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        note_data = {
            "student_id": student_id,
            "admin_id": profile.id,
            "school_id": profile.school_id,
            "note_text": request.note_text,
        }
        result = await supabase_client.query("admin_notes").insert(note_data).execute()
        return {"message": "Note added", "note": result["data"][0] if result.get("data") else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/admin/student/{student_id}/note/{note_id}")
async def delete_student_note(
        student_id: str,
        note_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin deletes a note"""
    try:
        await supabase_client.query("admin_notes").delete().eq("id", note_id).eq("school_id", profile.school_id).execute()
        return {"message": "Note deleted"}
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
        student_check = await supabase_client.query("profiles").select("*").eq("id", student_id).eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

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
            result = await supabase_client.query("profiles").update(update_data).eq("id", student_id).execute()
            if result.get("error"):
                raise Exception(result["error"])

        # Update class assignments (multi-class)
        if request.class_ids is not None:
            class_ids = [class_id for class_id in request.class_ids if class_id]
            unique_class_ids = list(dict.fromkeys(class_ids))

            if unique_class_ids:
                classes_result = await supabase_client.query("classes").select("id, year_level").in_("id", unique_class_ids).eq(
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

            await supabase_client.query("student_classes").delete().eq("student_id", student_id).execute()

            if unique_class_ids:
                insert_rows = [{"student_id": student_id, "class_id": class_id} for class_id in unique_class_ids]
                insert_result = await supabase_client.query("student_classes").insert(insert_rows).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        # Backwards-compatible single class assignment
        elif request.class_id is not None:
            class_id = request.class_id or None
            if class_id:
                class_check = await supabase_client.query("classes").select("id, year_level").eq("id", class_id).eq("school_id", profile.school_id).execute()
                if not class_check["data"]:
                    raise HTTPException(status_code=404, detail="Class not found")
                class_year_level = class_check["data"][0].get("year_level")
                if not class_year_level or class_year_level != effective_year_level:
                    raise HTTPException(status_code=400, detail="Class year level must match the student's year level")

            await supabase_client.query("student_classes").delete().eq("student_id", student_id).execute()

            if class_id:
                insert_result = await supabase_client.query("student_classes").insert({"student_id": student_id, "class_id": class_id}).execute()
                if insert_result.get("error"):
                    raise Exception(insert_result["error"])

        # Validate existing assignments when only year level changes
        elif request.year_level is not None:
            student_classes_result = await supabase_client.query("student_classes").select("class_id").eq("student_id", student_id).execute()
            existing_class_ids = [row["class_id"] for row in student_classes_result["data"]]

            if existing_class_ids:
                classes_result = await supabase_client.query("classes").select("id, year_level").in_("id", existing_class_ids).execute()
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
        student_check = await supabase_client.query("profiles").select("*").eq("id", student_id).eq("school_id", profile.school_id).eq("role", UserRole.STUDENT).execute()

        if not student_check["data"]:
            raise HTTPException(status_code=404, detail="Student not found")

        # Delete profile (cascades due to foreign keys)
        result = await supabase_client.query("profiles").delete().eq("id", student_id).execute()
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
        students_result = await supabase_client.query("profiles").select("id").eq("school_id", school_id).eq("role", UserRole.STUDENT).execute()
        total_students = len(students_result.get("data", []))

        # Count teachers
        teachers_result = await supabase_client.query("profiles").select("id").eq("school_id", school_id).eq("role", UserRole.TEACHER).execute()
        total_teachers = len(teachers_result.get("data", []))

        # Count classes
        classes_result = await supabase_client.query("classes").select("id").eq("school_id", school_id).execute()
        total_classes = len(classes_result.get("data", []))

        # Count assessments completed
        assessments_result = await supabase_client.query("assessment_results").select("user_id").eq("school_id", school_id).execute()
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

        result = await supabase_client.query("profiles").insert(profile_data).execute()

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
    start_time = time.time()
    try:
        # 1. Get all teachers for the school
        teachers_result = await supabase_client.query("profiles") \
            .select("id, full_name, email") \
            .eq("school_id", profile.school_id) \
            .eq("role", UserRole.TEACHER) \
            .execute()

        teachers = teachers_result.get("data", [])
        if not teachers:
            return {"teachers": []}

        teacher_map = {t["id"]: t for t in teachers}

        # 2. Get all classes for the school, with subjects embedded
        classes_result = await supabase_client.query("classes") \
            .select("*, subjects(id, name, category)") \
            .eq("school_id", profile.school_id) \
            .execute()

        classes = classes_result.get("data", [])

        # 3. Process classes and subjects in Python
        classes_by_teacher = {}
        subjects_by_teacher = {}
        for cls in classes:
            teacher_id = cls.get("teacher_id")
            if not teacher_id:
                continue

            # Group classes by teacher
            classes_by_teacher.setdefault(teacher_id, []).append(cls)

            # Group subjects by teacher
            subject = cls.get("subjects")
            if subject:
                subjects_by_teacher.setdefault(teacher_id, {})[subject["id"]] = subject

        # 4. Enrich the teacher data
        enriched_teachers = []
        for teacher_id, teacher in teacher_map.items():
            classes_taught = classes_by_teacher.get(teacher_id, [])
            subjects_taught_map = subjects_by_teacher.get(teacher_id, {})

            enriched_teachers.append({
                "id": teacher["id"],
                "full_name": teacher["full_name"],
                "email": teacher["email"],
                "classes_taught": classes_taught,
                "subjects_taught": list(subjects_taught_map.values()),
                "classes_count": len(classes_taught),
                "subjects_count": len(subjects_taught_map)
            })

        return {"teachers": enriched_teachers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        end_time = time.time()
        print(f"PERF: get_all_teachers took {end_time - start_time:.4f} seconds.")


@app.get("/admin/teacher/{teacher_id}")
async def get_teacher_details(
        teacher_id: str,
        profile: Profile = Depends(require_admin)
):
    """Admin gets detailed teacher information"""
    try:
        # Get teacher profile
        teacher_result = await supabase_client.query("profiles").select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
                                                                                                            UserRole.TEACHER).execute()

        if not teacher_result["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        teacher = teacher_result["data"][0]

        # Get classes taught
        classes_result = await supabase_client.query("classes").select("*").eq("teacher_id", teacher_id).execute()

        classes = classes_result["data"]

        # Get subjects from classes
        subject_ids = list(set([c["subject_id"] for c in classes]))

        subjects = []
        if subject_ids:
            subjects_result = await supabase_client.query("subjects").select("*").in_("id", subject_ids).execute()
            subjects = subjects_result["data"]

        # Get students in teacher's classes
        class_ids = [c["id"] for c in classes]

        students = []
        if class_ids:
            student_classes_result = await supabase_client.query("student_classes").select("student_id, class_id").in_("class_id", class_ids).execute()

            student_ids = list(set([sc["student_id"] for sc in student_classes_result["data"]]))

            if student_ids:
                students_result = await supabase_client.query("profiles").select("id, full_name, email, year_level").in_("id",
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

        result = await supabase_client.query("profiles").insert(profile_data).execute()

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
        teacher_check = await supabase_client.query("profiles").select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
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
        result = await supabase_client.query("profiles").update(update_data).eq("id", teacher_id).execute()

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
        teacher_check = await supabase_client.query("profiles").select("*").eq("id", teacher_id).eq("school_id", profile.school_id).eq("role",
                                                                                                           UserRole.TEACHER).execute()

        if not teacher_check["data"]:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Delete profile (cascades due to foreign keys)
        result = await supabase_client.query("profiles").delete().eq("id", teacher_id).execute()

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
            classes_result = await supabase_client.query("classes").select("id").eq("subject_id", existing["id"]).execute()

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
    start_time = time.time()
    try:
        # Get all classes (simple select, no embedding)
        classes_result = await supabase_client.query("classes") \
            .select("*") \
            .eq("school_id", profile.school_id) \
            .execute()

        if classes_result.get("error"):
            raise HTTPException(status_code=500, detail=f"DB error: {classes_result['error']}")

        classes = classes_result.get("data", [])

        if not classes:
            return {"classes": []}

        class_ids = [c["id"] for c in classes]
        subject_ids = list(set(c["subject_id"] for c in classes if c.get("subject_id")))
        teacher_ids = list(set(c["teacher_id"] for c in classes if c.get("teacher_id")))

        # Fetch subjects, teachers, and student counts separately
        subjects_map = {}
        if subject_ids:
            subjects_result = await supabase_client.query("subjects") \
                .select("id, name, category") \
                .in_("id", subject_ids) \
                .execute()
            for s in subjects_result.get("data", []):
                subjects_map[s["id"]] = s

        teachers_map = {}
        if teacher_ids:
            teachers_result = await supabase_client.query("profiles") \
                .select("id, full_name") \
                .in_("id", teacher_ids) \
                .execute()
            for t in teachers_result.get("data", []):
                teachers_map[t["id"]] = t

        student_classes_result = await supabase_client.query("student_classes") \
            .select("class_id") \
            .in_("class_id", class_ids) \
            .execute()

        student_counts = {}
        for sc in student_classes_result.get("data", []):
            class_id = sc["class_id"]
            student_counts[class_id] = student_counts.get(class_id, 0) + 1

        enriched_classes = []
        for cls in classes:
            subject = subjects_map.get(cls.get("subject_id"), {})
            teacher = teachers_map.get(cls.get("teacher_id"), {})

            enriched_classes.append({
                "id": cls["id"],
                "class_name": cls["class_name"],
                "year_level": cls.get("year_level"),
                "subject_name": subject.get("name", ""),
                "subject_category": subject.get("category", ""),
                "teacher_name": teacher.get("full_name", ""),
                "teacher_id": cls.get("teacher_id"),
                "subject_id": cls.get("subject_id"),
                "student_count": student_counts.get(cls["id"], 0)
            })

        return {"classes": enriched_classes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        end_time = time.time()
        print(f"PERF: get_all_classes took {end_time - start_time:.4f} seconds.")


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
        subject_check = await supabase_client.query("subjects").select("*").eq("id", subject_id).eq("school_id",
                                                                                profile.school_id).execute()

        if not subject_check["data"]:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Verify teacher exists and belongs to school
        teacher_check = await supabase_client.query("profiles").select("*").eq("id", request.teacher_id).eq("school_id", profile.school_id).eq(
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

        result = await supabase_client.query("classes").insert(class_data).execute()

        if result.get("error"):
            raise Exception(result["error"])

        class_id = result["data"][0]["id"]

        # Assign students (optional)
        if request.student_ids is not None:
            student_ids = [student_id for student_id in request.student_ids if student_id]
            unique_student_ids = list(dict.fromkeys(student_ids))

            if unique_student_ids:
                students_result = await supabase_client.query("profiles").select("id, year_level").in_("id", unique_student_ids).eq(
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
                insert_result = await supabase_client.query("student_classes").insert(insert_rows).execute()
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
        class_result = await supabase_client.query("classes").select("*").eq("id", class_id).eq("school_id", profile.school_id).execute()

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
                subject_check = await supabase_client.query("subjects").select("id").eq("id", resolved_subject_id).eq("school_id",
                                                                                        profile.school_id).execute()
                if not subject_check["data"]:
                    raise HTTPException(status_code=404, detail="Subject not found")

        if request.teacher_id is not None:
            teacher_check = await supabase_client.query("profiles").select("id").eq("id", request.teacher_id).eq("school_id",
                                                                                      profile.school_id).eq(
                "role", UserRole.TEACHER).execute()
            if not teacher_check["data"]:
                raise HTTPException(status_code=404, detail="Teacher not found")

        effective_year_level = request.year_level if request.year_level is not None else existing_class.get(
            "year_level"
        )

        if request.year_level is not None and request.student_ids is None:
            roster_result = await supabase_client.query("student_classes").select("student_id").eq("class_id", class_id).execute()
            roster_ids = [row["student_id"] for row in roster_result["data"]]

            if roster_ids:
                students_result = await supabase_client.query("profiles").select("id, year_level").in_("id", roster_ids).execute()
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
            result = await supabase_client.query("classes").update(update_data).eq("id", class_id).execute()
            if result.get("error"):
                raise Exception(result["error"])

        if request.student_ids is not None:
            student_ids = [student_id for student_id in request.student_ids if student_id]
            unique_student_ids = list(dict.fromkeys(student_ids))

            if unique_student_ids:
                students_result = await supabase_client.query("profiles").select("id, year_level").in_("id", unique_student_ids).eq(
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

            current_result = await supabase_client.query("student_classes").select("student_id").eq("class_id", class_id).execute()
            current_ids = [row["student_id"] for row in current_result["data"]]

            current_set = set(current_ids)
            requested_set = set(unique_student_ids)

            to_add = [student_id for student_id in unique_student_ids if student_id not in current_set]
            to_remove = [student_id for student_id in current_ids if student_id not in requested_set]

            if to_remove:
                delete_result = await supabase_client.query("student_classes").delete().eq("class_id", class_id).in_("student_id", to_remove).execute()
                if delete_result.get("error"):
                    raise Exception(delete_result["error"])

            if to_add:
                insert_rows = [{"student_id": student_id, "class_id": class_id} for student_id in to_add]
                insert_result = await supabase_client.query("student_classes").insert(insert_rows).execute()
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
        class_result = await supabase_client.query("classes").select("id").eq("id", class_id).eq("school_id", profile.school_id).execute()

        if not class_result["data"]:
            raise HTTPException(status_code=404, detail="Class not found")

        roster_delete = await supabase_client.query("student_classes").delete().eq("class_id", class_id).execute()
        if roster_delete.get("error"):
            raise Exception(roster_delete["error"])

        class_delete = await supabase_client.query("classes").delete().eq("id", class_id).execute()
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
        classes_result = await supabase_client.query("classes").select("*").eq("school_id", school_id).execute()

        classes = classes_result["data"]

        # Get all students with assessments
        assessments_result = await supabase_client.query("assessment_results").select("user_id, ranking").eq("school_id", school_id).execute()

        assessments_by_user = {a["user_id"]: a["ranking"] for a in assessments_result["data"]}

        # Get all students
        students_result = await supabase_client.query("profiles").select("id, full_name, email, year_level").eq("school_id", school_id).eq("role",
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
            student_classes_result = await supabase_client.query("student_classes").select("student_id").eq("class_id", class_id).execute()

            student_count = len(student_classes_result["data"])

            # Get subject name
            subject_result = await supabase_client.query("subjects").select("name, category").eq("id", cls["subject_id"]).execute()

            subject = subject_result["data"][0] if subject_result["data"] else {}

            # Get teacher name
            teacher_result = await supabase_client.query("profiles").select("full_name").eq("id", cls["teacher_id"]).execute()

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
# AI ANALYSIS ENDPOINTS
# ============================================================================


async def _get_teacher_status(student_id: str) -> dict:
    """
    Check how many of a student's teachers have submitted comments.
    Returns { total_teachers, commented_teachers, all_commented, missing }.
    """
    # Get student's class_ids
    sc_result = await supabase_client.query("student_classes") \
        .select("class_id") \
        .eq("student_id", student_id) \
        .execute()
    class_ids = [r["class_id"] for r in sc_result.get("data", [])]

    if not class_ids:
        return {
            "total_teachers": 0,
            "commented_teachers": 0,
            "all_commented": True,
            "missing": [],
        }

    # Get distinct teacher_ids from those classes
    classes_result = await supabase_client.query("classes") \
        .select("teacher_id") \
        .in_("id", class_ids) \
        .execute()
    all_teacher_ids = list(set(
        c["teacher_id"] for c in classes_result.get("data", []) if c.get("teacher_id")
    ))

    if not all_teacher_ids:
        return {
            "total_teachers": 0,
            "commented_teachers": 0,
            "all_commented": True,
            "missing": [],
        }

    # Get teacher_ids that have commented on this student
    comments_result = await supabase_client.query("teacher_comments") \
        .select("teacher_id") \
        .eq("student_id", student_id) \
        .execute()
    commented_teacher_ids = set(
        c["teacher_id"] for c in comments_result.get("data", []) if c.get("teacher_id")
    )

    missing_ids = [tid for tid in all_teacher_ids if tid not in commented_teacher_ids]

    # Get names for missing teachers
    missing_names = []
    if missing_ids:
        names_result = await supabase_client.query("profiles") \
            .select("id, full_name") \
            .in_("id", missing_ids) \
            .execute()
        missing_names = [
            {"id": t["id"], "name": t.get("full_name", "Unknown")}
            for t in names_result.get("data", [])
        ]

    return {
        "total_teachers": len(all_teacher_ids),
        "commented_teachers": len(commented_teacher_ids & set(all_teacher_ids)),
        "all_commented": set(all_teacher_ids).issubset(commented_teacher_ids),
        "missing": missing_names,
    }


@app.get("/student/teacher-status")
async def get_teacher_comment_status(
    profile: Profile = Depends(require_student)
):
    """Returns teacher comment status for the current student."""
    try:
        status = await _get_teacher_status(profile.id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ── Shared helpers for analysis endpoints ──────────────────────────

async def _load_teacher_comments(student_id: str) -> list[dict]:
    """Load teacher comments for a student, enriched with teacher name and subject."""
    comments_result = await supabase_client.query("teacher_comments") \
        .select("id, comment_text, performance_rating, engagement_rating, teacher_id, class_id") \
        .eq("student_id", student_id) \
        .execute()

    raw_comments = comments_result.get("data", [])
    if not raw_comments:
        return []

    # Batch-load teacher names
    teacher_ids = list(set(c["teacher_id"] for c in raw_comments if c.get("teacher_id")))
    teacher_name_map = {}
    if teacher_ids:
        teachers_result = await supabase_client.query("profiles") \
            .select("id, full_name") \
            .in_("id", teacher_ids) \
            .execute()
        teacher_name_map = {t["id"]: t.get("full_name", "Unknown") for t in teachers_result.get("data", [])}

    # Batch-load class→subject mapping
    class_ids = list(set(c["class_id"] for c in raw_comments if c.get("class_id")))
    subject_name_map = {}
    if class_ids:
        classes_result = await supabase_client.query("classes") \
            .select("id, subjects(name)") \
            .in_("id", class_ids) \
            .execute()
        for cls in classes_result.get("data", []):
            subj = cls.get("subjects")
            if subj:
                subject_name_map[cls["id"]] = subj["name"]

    teacher_comments = []
    for c in raw_comments:
        teacher_comments.append({
            "teacher_name": teacher_name_map.get(c.get("teacher_id"), "Unknown"),
            "subject_name": subject_name_map.get(c.get("class_id"), "Unknown"),
            "comment_text": c.get("comment_text", ""),
            "performance_rating": c.get("performance_rating"),
            "engagement_rating": c.get("engagement_rating"),
        })

    return teacher_comments


async def _load_subject_enrolments(student_id: str) -> list[dict]:
    """Load a student's subject enrolments from student_classes → classes → subjects."""
    sc_result = await supabase_client.query("student_classes") \
        .select("class_id, grade") \
        .eq("student_id", student_id) \
        .execute()

    enrollments = sc_result.get("data", [])
    if not enrollments:
        return []

    class_ids = [e["class_id"] for e in enrollments]
    grade_by_class = {e["class_id"]: e.get("grade") for e in enrollments}

    classes_result = await supabase_client.query("classes") \
        .select("id, year_level, subjects(name)") \
        .in_("id", class_ids) \
        .execute()

    subject_enrolments = []
    for cls in classes_result.get("data", []):
        subj = cls.get("subjects")
        if subj:
            subject_enrolments.append({
                "subject_name": subj["name"],
                "year_level": cls.get("year_level", "?"),
                "grade": grade_by_class.get(cls["id"]),
            })

    return subject_enrolments


def _map_analysis_for_frontend(row: dict) -> dict:
    """Map DB column names back to frontend field names."""
    row["strengths"] = row.get("strength_profile")
    row["gaps"] = row.get("gap_analysis")
    row["strength_narrative"] = row.get("overall_narrative")

    # Reconstruct career_explanations from stored final_ranking
    final_ranking = row.get("final_ranking") or []
    det_top20 = {e["soc_code"]: e["score"] for e in (row.get("deterministic_top20") or [])}
    career_explanations = {}
    for entry in final_ranking:
        soc = entry.get("soc_code", "")
        career_explanations[soc] = {
            "title": entry.get("career_name", ""),
            "score": det_top20.get(soc, 0),
            "rank": entry.get("rank", 0),
            "explanation": entry.get("reasoning", ""),
        }
    row["career_explanations"] = career_explanations
    return row


async def _store_analysis(student_id: str, school_id: str, answers: dict, result: dict):
    """Store analysis result in student_analyses table (upsert)."""
    import json as _json

    analysis_data = {
        "student_id": student_id,
        "school_id": school_id,
        "raw_answers": answers,
        "assessment_quality": result.get("assessment_quality"),
        "teacher_comments_snapshot": result.get("data_sources_used"),
        "subject_enrolments": None,
        "final_ranking": result.get("final_ranking", []),
        "strength_profile": result.get("strength_profile"),
        "gap_analysis": result.get("gap_analysis"),
        "conflict_notes": result.get("conflicts"),
        "weighting_explanation": _json.dumps(result.get("data_weighting")) if result.get("data_weighting") else None,
        "overall_narrative": result.get("overall_narrative"),
        "confidence_score": result.get("confidence_score", 0.5),
        "data_sources_used": result.get("data_sources_used"),
        "deterministic_top20": result.get("deterministic_top20"),
    }

    existing = await supabase_client.query("student_analyses") \
        .select("id, analysis_version") \
        .eq("student_id", student_id) \
        .execute()

    if existing.get("data"):
        current_version = existing["data"][0].get("analysis_version", 1)
        analysis_data["analysis_version"] = current_version + 1
        await supabase_client.query("student_analyses") \
            .update(analysis_data) \
            .eq("id", existing["data"][0]["id"]) \
            .execute()
    else:
        analysis_data["analysis_version"] = 1
        await supabase_client.query("student_analyses") \
            .insert(analysis_data) \
            .execute()


# ── Follow-up question endpoints ──────────────────────────────────

@app.post("/student/analysis/follow-up-questions")
async def check_follow_up_questions(
    request: AssessmentSubmission,
    profile: Profile = Depends(require_student),
):
    """
    Check if a student's assessment answers need follow-up questions.
    If the profile is ambiguous, generates targeted follow-up questions via AI.
    """
    try:
        answers = request.answers
        quality = check_assessment_quality(answers)

        if quality["confidence"] == "high":
            return {"needs_follow_up": False}

        questions = await generate_follow_up_questions(answers, quality)

        if not questions:
            # Groq failed or returned empty — graceful degradation
            return {"needs_follow_up": False}

        return {
            "needs_follow_up": True,
            "question_count": len(questions),
            "questions": questions,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Follow-up check error: {str(e)}")


class FollowUpSubmission(BaseModel):
    follow_up_answers: List[dict]


@app.post("/student/assessment/follow-up")
async def submit_follow_up_answers(
    request: FollowUpSubmission,
    profile: Profile = Depends(require_student),
):
    """
    Save follow-up answers to the student's assessment_results row.
    """
    try:
        # Verify student has an existing assessment
        existing = await supabase_client.query("assessment_results") \
            .select("user_id") \
            .eq("user_id", profile.id) \
            .execute()

        if not existing.get("data"):
            raise HTTPException(
                status_code=400,
                detail="No assessment found. Please complete the assessment first."
            )

        # Update with follow-up answers
        await supabase_client.query("assessment_results") \
            .update({"follow_up_answers": request.follow_up_answers}) \
            .eq("user_id", profile.id) \
            .execute()

        return {"status": "saved"}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Follow-up save error: {str(e)}")


# ── Analysis endpoints ─────────────────────────────────────────────

@app.post("/student/analysis")
async def trigger_student_analysis(
    profile: Profile = Depends(require_student)
):
    """
    Run full AI analysis for the current student.
    Requires all teachers to have commented first.
    """
    try:
        # Check teacher gating
        teacher_status = await _get_teacher_status(profile.id)
        if not teacher_status["all_commented"]:
            missing_count = teacher_status["total_teachers"] - teacher_status["commented_teachers"]
            raise HTTPException(
                status_code=400,
                detail=f"Waiting for {missing_count} teacher(s) to submit comments before analysis can run."
            )

        # Load assessment (including follow-up answers)
        assessment_result = await supabase_client.query("assessment_results") \
            .select("raw_answers, follow_up_answers") \
            .eq("user_id", profile.id) \
            .execute()

        if not assessment_result.get("data"):
            raise HTTPException(status_code=400, detail="No assessment found. Please complete the assessment first.")

        answers = assessment_result["data"][0].get("raw_answers", {})
        if not answers:
            raise HTTPException(status_code=400, detail="Assessment data is empty.")

        follow_up = assessment_result["data"][0].get("follow_up_answers")

        # Run deterministic engine → top 20
        user_profile = convert_answers_to_profile(answers)
        _results, raw_ranking = rank_profiles(user_profile)
        top_20 = raw_ranking[:20]

        # Load teacher comments (raw text for AI)
        comments = await _load_teacher_comments(profile.id)

        # Load subject enrolments
        subjects = await _load_subject_enrolments(profile.id)

        # Run AI analysis
        result = await run_analysis(answers, top_20, comments, subjects, follow_up_answers=follow_up)

        # Store in student_analyses
        await _store_analysis(profile.id, profile.school_id, answers, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.get("/student/analysis")
async def get_student_analysis(
    profile: Profile = Depends(require_student)
):
    """Retrieve stored analysis for the current student."""
    try:
        result = await supabase_client.query("student_analyses") \
            .select("*") \
            .eq("student_id", profile.id) \
            .execute()

        if not result.get("data"):
            return {"analysis": None}

        return {"analysis": _map_analysis_for_frontend(result["data"][0])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/student/{student_id}/analysis")
async def get_student_analysis_by_id(
    student_id: str,
    profile: Profile = Depends(require_profile)
):
    """Retrieve stored analysis for a student. Accessible by the student, their teachers, or admin."""
    try:
        # Verify access: student can view own, admin can view school, teacher can view their students
        if profile.role == "student" and profile.id != student_id:
            raise HTTPException(status_code=403, detail="You can only view your own analysis.")
        elif profile.role == "admin":
            student_check = await supabase_client.query("profiles") \
                .select("id").eq("id", student_id).eq("school_id", profile.school_id).execute()
            if not student_check.get("data"):
                raise HTTPException(status_code=404, detail="Student not found in your school.")

        result = await supabase_client.query("student_analyses") \
            .select("*") \
            .eq("student_id", student_id) \
            .execute()

        if not result.get("data"):
            return {"analysis": None}

        return {"analysis": _map_analysis_for_frontend(result["data"][0])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/admin/trigger-analysis/{student_id}")
async def admin_trigger_analysis(
    student_id: str,
    profile: Profile = Depends(require_admin)
):
    """Admin triggers re-analysis for a student (bypasses teacher gating)."""
    try:
        # Verify student belongs to school
        student_check = await supabase_client.query("profiles") \
            .select("id, school_id") \
            .eq("id", student_id) \
            .eq("school_id", profile.school_id) \
            .execute()

        if not student_check.get("data"):
            raise HTTPException(status_code=404, detail="Student not found")

        # Load assessment (including follow-up answers)
        assessment_result = await supabase_client.query("assessment_results") \
            .select("raw_answers, follow_up_answers") \
            .eq("user_id", student_id) \
            .execute()

        if not assessment_result.get("data"):
            raise HTTPException(status_code=400, detail="No assessment found for this student.")

        answers = assessment_result["data"][0].get("raw_answers", {})
        if not answers:
            raise HTTPException(status_code=400, detail="Assessment data is empty.")

        follow_up = assessment_result["data"][0].get("follow_up_answers")

        # Run deterministic engine → top 20
        user_profile = convert_answers_to_profile(answers)
        _results, raw_ranking = rank_profiles(user_profile)
        top_20 = raw_ranking[:20]

        # Load teacher comments (no gating check)
        comments = await _load_teacher_comments(student_id)

        # Load subject enrolments
        subjects = await _load_subject_enrolments(student_id)

        # Run AI analysis
        result = await run_analysis(answers, top_20, comments, subjects, follow_up_answers=follow_up)

        # Store result
        await _store_analysis(student_id, profile.school_id, answers, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


# ── Test endpoints (no auth, for development) ──────────────────────

@app.post("/test/follow-up-questions")
async def test_follow_up_questions(request: AssessmentSubmission):
    """
    Test endpoint for follow-up question generation.
    No authentication required — for development only.
    """
    try:
        answers = request.answers
        quality = check_assessment_quality(answers)

        if quality["confidence"] == "high":
            return {"needs_follow_up": False, "quality": quality}

        questions = await generate_follow_up_questions(answers, quality)

        if not questions:
            return {"needs_follow_up": False, "quality": quality}

        return {
            "needs_follow_up": True,
            "question_count": len(questions),
            "questions": questions,
            "quality": quality,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Follow-up check error: {str(e)}")


class TestAnalysisRequest(BaseModel):
    """Test analysis request — accepts arbitrary data without auth."""
    answers: Dict[str, int]
    teacher_comments: Optional[List[dict]] = []
    subject_enrolments: Optional[List[dict]] = []
    follow_up_answers: Optional[List[dict]] = None


@app.post("/test/analysis")
async def test_analysis(request: TestAnalysisRequest):
    """
    Test endpoint for the AI analysis pipeline.
    Accepts arbitrary answers, teacher comments, and subjects.
    No authentication required — for development and demonstration only.
    """
    try:
        answers = request.answers

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

        # Run deterministic engine → top 20
        user_profile = convert_answers_to_profile(answers)
        _results, raw_ranking = rank_profiles(user_profile)
        top_20 = raw_ranking[:20]

        # Run AI analysis with provided data
        result = await run_analysis(
            answers=answers,
            top_20=top_20,
            teacher_comments=request.teacher_comments or [],
            subject_enrolments=request.subject_enrolments or [],
            follow_up_answers=request.follow_up_answers,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
