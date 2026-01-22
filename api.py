from fastapi import FastAPI
from typing import Dict
from link.service import run_assessment
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://YOUR_FRONTEND.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/assessment")
def assess(answers: Dict[str, int]):
    ranking = run_assessment(answers)
    return {"ranking": ranking}
