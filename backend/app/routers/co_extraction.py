"""Faculty-only course outcome extraction preview."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..db import get_conn
from ..deps import require_faculty
from ..services.co_extraction import extract_cos_from_pdf, extract_cos_from_pptx, extract_cos_from_jpg, extract_cos_from_ppt
from .subjects import _subject_owned

router = APIRouter(tags=["course-outcome-extraction"])

MAX_CO_FILE_SIZE = 10 * 1024 * 1024


@router.post("/subjects/{subject_id}/cos/extract")
async def extract_course_outcomes(
    subject_id: str,
    file: UploadFile = File(...),
    faculty=Depends(require_faculty),
    conn=Depends(get_conn),
):
    filename = (file.filename or "").lower().strip()

    if not filename.endswith((".pdf", ".ppt", ".pptx", ".jpg", ".jpeg")):
        raise HTTPException(
            400, "Upload a PDF, PPT, PPTX, or JPG file."
        )

    content = await file.read(MAX_CO_FILE_SIZE + 1)

    if len(content) > MAX_CO_FILE_SIZE:
        raise HTTPException(
            413, "File must be 10 MB or smaller."
        )

    is_pdf = filename.endswith(".pdf")
    is_ppt = filename.endswith(".ppt")
    is_pptx = filename.endswith(".pptx")
    is_jpg = filename.endswith((".jpg", ".jpeg"))

    if is_pdf and not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF file.")

    if is_ppt and not content.startswith(
        bytes.fromhex("D0CF11E0A1B11AE1")
    ):
        raise HTTPException(400, "Invalid PPT file.")

    if is_pptx and not content.startswith(b"PK"):
        raise HTTPException(400, "Invalid PPTX file.")

    if is_jpg and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(400, "Invalid JPG file.")

    _subject_owned(conn, subject_id, faculty["user_id"])

    try:
        if is_pdf:
            cos = extract_cos_from_pdf(content)
        elif is_ppt:
            cos = extract_cos_from_ppt(content)
        elif is_pptx:
            cos = extract_cos_from_pptx(content)
        else:
            cos = extract_cos_from_jpg(content)
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
