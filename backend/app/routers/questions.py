import json
from uuid import UUID

from fastapi import APIRouter, Depends, Body, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError

router = APIRouter(tags=["questions"])


class BatchQuestion(BaseModel):
    module_id: UUID
    co_id: UUID | None = None
    stem: str
    options: list[str]
    correct_option: int
    explanation: str | None = None
    marks: float = 1
    difficulty: str | None = None
    bloom_level: str | None = None
    source_slide_number: int | None = Field(default=None, gt=0, strict=True)
    source_quote: str | None = None


class QuestionBatch(BaseModel):
    questions: list[BatchQuestion]


class QuestionResponse(BatchQuestion):
    id: UUID
    co_id: UUID | None
    co_number: int | None
    status: str
    source: str
    created_by: UUID | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_question(row) -> dict:
    return {
        "id": str(row["id"]),
        "module_id": str(row["module_id"]),
        "co_id": str(row["co_id"]) if row["co_id"] is not None else None,
        "co_number": row["co_number"],
        "stem": row["stem"],
        "options": list(row["options"]),
        "correct_option": row["correct_option"],
        "explanation": row["explanation"],
        "marks": float(row["marks"]) if row["marks"] else None,
        "difficulty": row["difficulty"],
        "bloom_level": row["bloom_level"],
        "source_slide_number": row["source_slide_number"],
        "source_quote": row["source_quote"],
        "status": row["status"],
        "source": row["source"],
        "created_by": str(row["created_by"]) if row["created_by"] else None,
    }


def _validate_module_and_co(conn, module_id, co_id, faculty_user_id, *, original_subject=None):
    """Check module ownership and, when supplied, CO subject membership."""
    stmt = text(
        "SELECT m.subject_id AS subject_id "
        "FROM modules m JOIN subjects s ON s.id = m.subject_id "
        "WHERE m.id = :mid AND s.faculty_user_id = :fid"
    )
    mod = conn.execute(stmt, {"mid": module_id, "fid": faculty_user_id}).mappings().fetchone()
    if mod is None or (original_subject is not None and mod["subject_id"] != original_subject):
        raise AppError(404, "NOT_FOUND", "Module not found")

    # Check CO belongs to the same subject
    if co_id is None:
        return
    co = conn.execute(
        text(
            "SELECT id, number FROM course_outcomes "
            "WHERE id = :cid AND subject_id = :sid"
        ),
        {"cid": str(co_id), "sid": str(mod["subject_id"])},
    ).mappings().fetchone()
    if co is None:
        raise AppError(404, "NOT_FOUND", "CO not found or does not belong to the module's subject")
    return co


def _question_owned(conn, question_id: str, faculty_user_id: str):
    """Return the question row (with co_number) if the faculty owns the
    subject it belongs to, else raise 404."""
    row = conn.execute(
        text(
            "SELECT q.*, m.subject_id, co.number AS co_number FROM questions q "
            "JOIN modules m ON m.id = q.module_id "
            "JOIN subjects s ON s.id = m.subject_id "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :qid AND s.faculty_user_id = :fid FOR UPDATE OF q"
        ),
        {"qid": str(question_id), "fid": faculty_user_id},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Question not found")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/questions", response_model=list[QuestionResponse])
def list_questions(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    module_id: str = Query(...),
    co_id: str | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
):
    # Verify faculty owns the subject of this module
    mod = conn.execute(
        text(
            "SELECT m.id FROM modules m "
            "JOIN subjects s ON s.id = m.subject_id "
            "WHERE m.id = :mid AND s.faculty_user_id = :fid"
        ),
        {"mid": str(module_id), "fid": faculty["user_id"]},
    ).mappings().fetchone()
    if mod is None:
        raise AppError(404, "NOT_FOUND", "Module not found")

    where = ["q.module_id = :mid"]
    params: dict = {"mid": str(module_id)}
    if co_id:
        where.append("q.co_id = :cid")
        params["cid"] = str(co_id)
    if status:
        where.append("q.status = :status")
        params["status"] = status
    if source:
        where.append("q.source = :src")
        params["src"] = source

    rows = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE " + " AND ".join(where) + " ORDER BY q.created_at"
        ),
        params,
    ).mappings().fetchall()
    return [_row_to_question(r) for r in rows]


@router.post("/questions", status_code=201, response_model=QuestionResponse)
def create_question(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    module_id = payload.get("module_id")
    co_id = payload.get("co_id")
    stem = payload.get("stem")
    options = payload.get("options")
    correct_option = payload.get("correct_option")

    if module_id is None or co_id is None:
        raise AppError(400, "BAD_REQUEST", "module_id and co_id are required")
    if not stem or not options or correct_option is None:
        raise AppError(400, "BAD_REQUEST", "stem, options and correct_option are required")

    # Validate module + CO ownership
    _validate_module_and_co(conn, module_id, co_id, faculty["user_id"])

    result = conn.execute(
        text(
            "INSERT INTO questions "
            "(module_id, co_id, stem, options, correct_option, explanation, "
            "marks, difficulty, bloom_level, source, created_by) "
            "VALUES "
            "(:module_id, :co_id, :stem, CAST(:opts AS jsonb), :correct_option, :explanation, "
            ":marks, :difficulty, :bloom_level, 'faculty', :created_by) "
            "RETURNING * "
            "-- co_number join"
        ),
        {
            "module_id": str(module_id),
            "co_id": str(co_id),
            "stem": stem,
            "opts": json.dumps(options),
            "correct_option": correct_option,
            "explanation": payload.get("explanation"),
            "marks": payload.get("marks", 1),
            "difficulty": payload.get("difficulty"),
            "bloom_level": payload.get("bloom_level"),
            "created_by": faculty["user_id"],
        },
    )
    row = result.mappings().fetchone()

    # Re-fetch with co_number join
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": str(row["id"])},
    ).mappings().fetchone()
    return _row_to_question(full)


@router.post("/questions/batch", status_code=201, response_model=list[QuestionResponse])
def create_questions_batch(
    payload: QuestionBatch,
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    if not payload.questions:
        raise AppError(400, "BAD_REQUEST", "Expected a non-empty 'questions' array")

    created = []
    for index, q in enumerate(payload.questions, start=1):
        _validate_module_and_co(conn, q.module_id, q.co_id, faculty["user_id"])

        # Older batch clients have no citations. If a client supplies evidence,
        # validate it against the selected module, not against client-provided slides.
        if q.source_slide_number is not None or q.source_quote is not None:
            from ai.quiz_generation import QuizGenerationError, validate_slide_evidence

            slide = conn.execute(text(
                "SELECT text FROM content_chunks WHERE module_id = :mid AND slide_number = :slide"
            ), {"mid": q.module_id, "slide": q.source_slide_number}).scalar_one_or_none()
            if slide is None or not 0 <= q.correct_option < len(q.options):
                raise AppError(422, "INVALID_EVIDENCE", "Invalid source slide or correct option")
            try:
                validate_slide_evidence(q.model_dump(), index, {q.source_slide_number: ' '.join(slide.split())},
                                        q.stem, q.options[q.correct_option])
            except QuizGenerationError as exc:
                raise AppError(422, "INVALID_EVIDENCE", str(exc)) from exc

        result = conn.execute(
            text(
                "INSERT INTO questions "
                "(module_id, co_id, stem, options, correct_option, explanation, "
                "marks, difficulty, bloom_level, source, created_by, source_slide_number, source_quote) "
                "VALUES "
                "(:module_id, :co_id, :stem, CAST(:opts AS jsonb), :correct_option, :explanation, "
                ":marks, :difficulty, :bloom_level, 'AI', :created_by, :source_slide_number, :source_quote) "
                "RETURNING id"
            ),
            {
                **q.model_dump(exclude={"options"}),
                "opts": json.dumps(q.options),
                "created_by": faculty["user_id"],
            },
        )
        qid = str(result.mappings().fetchone()["id"])
        created.append(qid)

    # Fetch all created questions with co_number
    placeholders = ", ".join(f"'{q}'" for q in created)
    rows = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id IN (" + placeholders + ") ORDER BY q.created_at"
        ),
    ).mappings().fetchall()
    return [_row_to_question(r) for r in rows]


@router.patch("/questions/{id}", response_model=QuestionResponse)
def update_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    return _update_question(conn, id, faculty["user_id"], payload)


def _update_question(conn, id, faculty_id, payload):
    row = _question_owned(conn, id, faculty_id)

    updatable = {"stem", "options", "correct_option", "explanation",
                 "marks", "difficulty", "bloom_level", "co_id", "module_id",
                 "status", "source"}
    updates = {k: v for k, v in payload.items() if k in updatable}

    if not updates:
        return _row_to_question(row)

    co_id = updates.get("co_id", row["co_id"])
    if updates.get("status", row["status"]) == "approved" and co_id is None:
        raise AppError(409, "CONFLICT", "Assign a course outcome before approving the question")

    if "co_id" in updates or "module_id" in updates or updates.get("status") == "approved":
        _validate_module_and_co(conn, updates.get("module_id", row["module_id"]), co_id,
                                faculty_id, original_subject=row["subject_id"])

    # Historical quiz reports resolve a question's mapping from its current row.
    if any(k in updates and str(updates[k]) != str(row[k]) for k in ("co_id", "module_id")):
        used = conn.execute(text(
            "SELECT 1 FROM quiz_questions qq JOIN quizzes z ON z.id = qq.quiz_id "
            "WHERE qq.question_id = :id AND (z.published OR z.published_at IS NOT NULL "
            "OR EXISTS (SELECT 1 FROM quiz_attempts a WHERE a.quiz_id = z.id)) LIMIT 1"
        ), {"id": id}).scalar()
        if used:
            raise AppError(409, "CONFLICT", "Cannot remap a question used in quiz history")

    if "module_id" in updates and str(updates["module_id"]) != str(row["module_id"]):
        # A slide number only has meaning within its source module.
        updates.update(source_slide_number=None, source_quote=None)

    # Build SET clause, handling jsonb columns
    set_parts = []
    params = {}
    for k, v in updates.items():
        if k == "options":
            set_parts.append("options = CAST(:opts AS jsonb)")
            params["opts"] = json.dumps(v) if not isinstance(v, str) else v
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v
    set_clause = ", ".join(set_parts)
    params["id"] = id
    params["fid"] = faculty_id

    result = conn.execute(
        text(
            f"UPDATE questions SET {set_clause} "
            "FROM modules m JOIN subjects s ON s.id = m.subject_id "
            "WHERE questions.id = :id AND m.id = questions.module_id "
            "AND s.faculty_user_id = :fid "
            "RETURNING questions.*"
        ),
        params,
    )
    updated = result.mappings().fetchone()
    if updated is None:
        raise AppError(404, "NOT_FOUND", "Question not found")

    # Re-fetch with co_number
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": id},
    ).mappings().fetchone()
    return _row_to_question(full)


@router.post("/questions/{id}/approve", response_model=QuestionResponse)
def approve_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    return _update_question(conn, id, faculty["user_id"], {"status": "approved"})


@router.post("/questions/{id}/reject", response_model=QuestionResponse)
def reject_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    return _update_question(conn, id, faculty["user_id"], {"status": "rejected"})
