"""Faculty-only course outcome extraction preview."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..services.co_extraction import extract_cos_from_pdf

router = APIRouter(tags=["course-outcome-extraction"])

MAX_PDF_SIZE = 10 * 1024 * 1024


@router.post("/subjects/{subject_id}/cos/extract")
async def extract_course_outcomes(
    subject_id: str,
    file: UploadFile = File(...),
    faculty=Depends(require_faculty),
    conn=Depends(get_conn),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF file.")

    content = await file.read(MAX_PDF_SIZE + 1)

    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(413, "PDF must be 10 MB or smaller.")

    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF file.")

    faculty_id = str(faculty["id"])

    subject = conn.execute(
        text(
            "SELECT id FROM subjects "
            "WHERE id = :subject_id AND faculty_user_id = :faculty_id"
        ),
        {"subject_id": subject_id, "faculty_id": faculty_id},
    ).fetchone()

    if subject is None:
        raise HTTPException(404, "Subject not found.")

    try:
        cos = extract_cos_from_pdf(content)
    except Exception as exc:
        raise HTTPException(
            422, f"Could not extract course outcomes: {exc}"
        ) from exc

    return {
        "subject_id": subject_id,
        "filename": file.filename,
        "cos": cos,
        "count": len(cos),
        "requires_review": True,
        "saved": False,
    }
