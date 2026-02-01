import os
from typing import Dict, Any
from dotenv import load_dotenv

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from link.service import run_assessment, build_profile_from_ans
from portfolio.analysis import analyse_portfolio
from scripts.format import format_text

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors


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


@app.get("/portfolio/export/pdf")
def export_portfolio_pdf(user_id: str):
    portfolio = supabase_select_one(
        "portfolio_snapshots", "user_id", user_id
    )

    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail="Portfolio not found",
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Define custom styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor('#3498db'),
        borderPadding=8,
        leftIndent=0,
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        leading=14,
        leftIndent=0,
    )

    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        leftIndent=20,
        bulletIndent=10,
        leading=14,
    )

    # Build document content
    story = [Paragraph("Professional Portfolio", title_style)]

    # Date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#7f8c8d'),
        alignment=TA_CENTER,
        spaceAfter=30,
    )
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y')}",
        date_style
    ))

    # Divider line
    story.append(Spacer(1, 0.2 * inch))

    # Bio/Summary
    if portfolio.get("bio"):
        story.append(Paragraph("Professional Summary", heading_style))
        story.append(Paragraph(portfolio["bio"], body_style))
        story.append(Spacer(1, 0.3 * inch))

    # Strengths
    story.append(Paragraph("Key Strengths", heading_style))
    strengths = portfolio.get("strengths", [])
    if strengths:
        for s in strengths:
            text = format_text(s.get('signal', ''))
            story.append(Paragraph(f"• {text}", bullet_style))
    else:
        story.append(Paragraph("No strengths listed", body_style))

    story.append(Spacer(1, 0.3 * inch))

    # Growth Areas (formerly Gaps)
    story.append(Paragraph("Areas for Growth", heading_style))
    gaps = portfolio.get("gaps", [])
    if gaps:
        for g in gaps:
            text = format_text(g.get('signal', ''))
            story.append(Paragraph(f"• {text}", bullet_style))
    else:
        story.append(Paragraph("No growth areas identified", body_style))

    # Projects
    projects = portfolio.get("projects", [])
    if projects:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Notable Projects", heading_style))

        for p in projects:
            title = p.get("title") or "Untitled project"
            story.append(Paragraph(f"• {format_text(title, False)}", bullet_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=professional_portfolio.pdf"
        },
    )

