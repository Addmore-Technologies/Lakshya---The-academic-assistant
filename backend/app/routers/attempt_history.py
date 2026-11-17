from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..db import get_conn
from ..deps import get_current_user, require_faculty
from ..errors import AppError

router = APIRouter(tags=["attempt-history"])


def _serialize(row):
    return {
        "attempt_id": str(row["attempt_id"]),
        "quiz_id": str(row["quiz_id"]),
        "quiz_title": row["quiz_title"],
        "student_id": str(row["student_id"]),
        "usn": row["usn"],
        "student_name": row["student_name"],
        "subject_id": str(row["subject_id"]),
        "teaching_assignment_id": (
            str(row["teaching_assignment_id"])
            if row["teaching_assignment_id"] else None
        ),
        "section": row["section"],
        "attempt_number": row["attempt_number"],
        "total_score": (
            float(row["total_score"])
            if row["total_score"] is not None else None
        ),
        "max_score": (
            float(row["max_score"])
            if row["max_score"] is not None else None
        ),
        "started_at": (
            row["started_at"].isoformat()
            if row["started_at"] else None
        ),
        "submitted_at": (
            row["submitted_at"].isoformat()
            if row["submitted_at"] else None
        ),
        "answers": (
            row["answers"] if row["submitted_at"] is not None else None
        ),
    }


HISTORY_SQL = """
    SELECT
        qa.id AS attempt_id,
        qa.quiz_id,
        q.title AS quiz_title,
        qa.student_id,
        s.usn,
        s.name AS student_name,
        q.subject_id,
        qa.teaching_assignment_id,
        ta.section,
        qa.attempt_number,
        qa.total_score,
        qa.max_score,
        qa.started_at,
        qa.submitted_at,
        qa.answers
    FROM quiz_attempts qa
    JOIN quizzes q ON q.id = qa.quiz_id
    JOIN students s ON s.id = qa.student_id
    LEFT JOIN teaching_assignments ta
        ON ta.id = qa.teaching_assignment_id
"""


@router.get("/students/me/attempts")
def my_attempt_history(
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
):
    if current_user["role"] != "student":
        raise AppError(
            403, "FORBIDDEN", "Student access required"
        )

    rows = conn.execute(
        text(
            HISTORY_SQL
            + """
            WHERE qa.student_id = :student_id
            ORDER BY qa.started_at DESC
            """
        ),
        {"student_id": current_user["student_id"]},
    ).mappings().all()

    return [_serialize(row) for row in rows]


@router.get("/teaching-assignments/{assignment_id}/attempts")
def class_attempt_history(
    assignment_id: str,
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = conn.execute(
        text("""
            SELECT ta.id, ta.subject_id
            FROM teaching_assignments ta
            JOIN subjects sub ON sub.id = ta.subject_id
            WHERE ta.id = :assignment_id
              AND sub.faculty_user_id = :faculty_id
        """),
        {
            "assignment_id": assignment_id,
            "faculty_id": faculty["user_id"],
        },
    ).first()

    if assignment is None:
        raise AppError(
            404, "NOT_FOUND", "Teaching assignment not found"
        )

    rows = conn.execute(
        text(
            HISTORY_SQL
            + """
            WHERE qa.teaching_assignment_id = :assignment_id
              AND q.subject_id = :subject_id
            ORDER BY qa.started_at DESC
            """
        ),
        {
            "assignment_id": assignment_id,
            "subject_id": assignment["subject_id"],
        },
    ).mappings().all()

    return [_serialize(row) for row in rows]
