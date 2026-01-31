import os
from typing import Dict, Any
from dotenv import load_dotenv

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from link.service import run_assessment, build_profile_from_ans
from portfolio.analysis import analyse_portfolio


# -------------------------------------------------------------------
# App setup
# -------------------------------------------------------------------

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://launchpad-next-tau.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# Supabase REST configuration (NO supabase-py)
# -------------------------------------------------------------------

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]


def supabase_upsert(table: str, record: Dict[str, Any]) -> None:
    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    response = requests.post(url, headers=headers, json=record)

    if response.status_code not in (200, 201, 204):
        raise HTTPException(
            status_code=500,
            detail=f"Supabase error {response.status_code}: {response.text}",
        )


def supabase_select_one(table: str, column: str, value: str) -> Dict[str, Any] | None:
    url = f"{SUPABASE_URL}/rest/v1/{table}?{column}=eq.{value}&limit=1"

    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase error {response.status_code}: {response.text}",
        )

    data = response.json()
    return data[0] if data else None


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/assessment")
def assess(answers: Dict[str, int]):
    ranking = run_assessment(answers)
    return {"ranking": ranking}


@app.post("/portfolio/generate")
def generate_portfolio(answers: Dict[str, int]):
    try:
        profile = build_profile_from_ans(answers)
        return analyse_portfolio(profile)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/portfolio/save")
def save_portfolio(payload: Dict[str, Any]):
    required_fields = {"user_id", "strengths", "gaps"}

    if not required_fields.issubset(payload):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {required_fields - payload.keys()}",
        )

    record = {
        "user_id": payload["user_id"],
        "strengths": payload["strengths"],
        "gaps": payload["gaps"],
        "projects": payload.get("projects", []),
        "bio": payload.get("bio"),
    }

    supabase_upsert("portfolio_snapshots", record)

    return {"ok": True}


@app.get("/portfolio")
def get_portfolio(user_id: str):
    return supabase_select_one("portfolio_snapshots", "user_id", user_id)
