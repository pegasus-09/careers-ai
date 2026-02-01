from datetime import datetime
from io import BytesIO

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

