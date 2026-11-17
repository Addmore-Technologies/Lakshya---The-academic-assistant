from fastapi import APIRouter, Body, Depends
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError

router = APIRouter(tags=["teaching-assignments"])


def _owned_assignment(conn, assignment_id, faculty_id):
    row = conn.execute(
        text("""
            SELECT ta.*, s.code, s.name AS subject_name, s.semester
            FROM teaching_assignments ta
            JOIN subjects s ON s.id = ta.subject_id
            WHERE ta.id = :id AND s.faculty_user_id = :faculty_id
        """),
        {"id": assignment_id, "faculty_id": faculty_id},
    ).mappings().first()

    if row is None:
        raise AppError(404, "NOT_FOUND", "Teaching assignment not found")
    return row


def _serialize(row):
    return {
        "id": str(row["id"]),
        "subject_id": str(row["subject_id"]),
        "section": row["section"],
        "active": row["status"] == "active",
        "status": row["status"],
        "code": row["code"],
        "subject_name": row["subject_name"],
        "semester": row["semester"],
    }


@router.post("/teaching-assignments", status_code=201)
def create_assignment(
    payload: dict = Body(...),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    subject_id = payload.get("subject_id")
    section = str(payload.get("section") or "").strip().upper()

    if not subject_id or not section or len(section) > 20:
        raise AppError(
            422, "VALIDATION_ERROR",
            "Valid subject_id and section are required",
        )

    subject = conn.execute(
        text("""
            SELECT id FROM subjects
            WHERE id = :subject_id AND faculty_user_id = :faculty_id
        """),
        {"subject_id": subject_id, "faculty_id": faculty["user_id"]},
    ).mappings().first()

    if subject is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")

    existing = conn.execute(
        text("""
            SELECT id FROM teaching_assignments
            WHERE subject_id = :subject_id
              AND section = :section
              AND status = 'active'
        """),
        {"subject_id": subject_id, "section": section},
    ).first()

    if existing:
        raise AppError(
            409, "CONFLICT",
            "An active assignment already exists for this section",
        )

    row = conn.execute(
        text("""
            INSERT INTO teaching_assignments (subject_id, section, status)
            VALUES (:subject_id, :section, 'active')
            RETURNING id
        """),
        {"subject_id": subject_id, "section": section},
    ).mappings().first()

    return get_assignment(str(row["id"]), conn, faculty)


@router.get("/teaching-assignments")
def list_assignments(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    rows = conn.execute(
        text("""
            SELECT ta.*, s.code, s.name AS subject_name, s.semester
            FROM teaching_assignments ta
            JOIN subjects s ON s.id = ta.subject_id
            WHERE s.faculty_user_id = :faculty_id
            ORDER BY s.semester, s.code, ta.section
        """),
        {"faculty_id": faculty["user_id"]},
    ).mappings().all()

    return [_serialize(row) for row in rows]


@router.get("/teaching-assignments/{assignment_id}")
def get_assignment(
    assignment_id: str,
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    row = _owned_assignment(conn, assignment_id, faculty["user_id"])
    return _serialize(row)


@router.delete("/teaching-assignments/{assignment_id}")
def archive_assignment(
    assignment_id: str,
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    _owned_assignment(conn, assignment_id, faculty["user_id"])

    conn.execute(
        text("""
            UPDATE teaching_assignments
            SET status = 'archived', updated_at = now()
            WHERE id = :id
        """),
        {"id": assignment_id},
    )

    return {"id": assignment_id, "active": False, "status": "archived"}


@router.patch("/teaching-assignments/{assignment_id}")
def update_assignment(
    assignment_id: str,
    payload: dict = Body(...),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = _owned_assignment(
        conn, assignment_id, faculty["user_id"]
    )

    if assignment["status"] != "active":
        raise AppError(
            409, "CONFLICT", "Archived classes cannot be edited"
        )

    section = str(payload.get("section") or "").strip().upper()

    if not section or len(section) > 20:
        raise AppError(
            422, "VALIDATION_ERROR", "A valid section is required"
        )

    if section == assignment["section"]:
        return _serialize(assignment)

    existing = conn.execute(
        text("""
            SELECT id
            FROM teaching_assignments
            WHERE subject_id = :subject_id
              AND section = :section
              AND status = 'active'
              AND id <> :assignment_id
        """),
        {
            "subject_id": assignment["subject_id"],
            "section": section,
            "assignment_id": assignment_id,
        },
    ).first()

    if existing:
        raise AppError(
            409, "CONFLICT",
            "An active class already exists for this section",
        )

    # Keep the existing enrollment section labels consistent.
    conn.execute(
        text("""
            UPDATE enrollments
            SET section = :section
            WHERE teaching_assignment_id = :assignment_id
        """),
        {
            "section": section,
            "assignment_id": assignment_id,
        },
    )

    conn.execute(
        text("""
            UPDATE teaching_assignments
            SET section = :section, updated_at = now()
            WHERE id = :assignment_id
        """),
        {
            "section": section,
            "assignment_id": assignment_id,
        },
    )

    return get_assignment(assignment_id, conn, faculty)


@router.get("/teaching-assignments/{assignment_id}/roster")
def get_assignment_roster(
    assignment_id: str,
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = _owned_assignment(
        conn, assignment_id, faculty["user_id"]
    )

    rows = conn.execute(
        text("""
            SELECT
                s.id AS student_id,
                s.usn,
                s.name,
                e.section,
                e.created_at AS enrolled_at
            FROM enrollments e
            JOIN students s ON s.id = e.student_id
            WHERE e.teaching_assignment_id = :assignment_id
              AND e.subject_id = :subject_id
            ORDER BY s.usn
        """),
        {
            "assignment_id": assignment_id,
            "subject_id": assignment["subject_id"],
        },
    ).mappings().all()

    return {
        "teaching_assignment": _serialize(assignment),
        "total_students": len(rows),
        "students": [
            {
                "student_id": str(row["student_id"]),
                "usn": row["usn"],
                "name": row["name"],
                "section": row["section"],
                "enrolled_at": row["enrolled_at"].isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/teaching-assignments/{assignment_id}/students", status_code=201)
def enroll_student_in_assignment(
    assignment_id: str,
    payload: dict = Body(...),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = _owned_assignment(
        conn, assignment_id, faculty["user_id"]
    )

    if assignment["status"] != "active":
        raise AppError(
            409, "CONFLICT", "Cannot enroll into an archived class"
        )

    usn = str(payload.get("usn") or "").strip().upper()

    if not usn:
        raise AppError(422, "VALIDATION_ERROR", "USN is required")

    student = conn.execute(
        text("SELECT id, usn, name FROM students WHERE usn = :usn"),
        {"usn": usn},
    ).mappings().first()

    if student is None:
        raise AppError(404, "NOT_FOUND", "Student not found")

    existing = conn.execute(
        text("""
            SELECT id, teaching_assignment_id
            FROM enrollments
            WHERE student_id = :student_id
              AND subject_id = :subject_id
        """),
        {
            "student_id": student["id"],
            "subject_id": assignment["subject_id"],
        },
    ).mappings().first()

    if existing:
        raise AppError(
            409, "CONFLICT",
            "Student is already enrolled in this subject"
        )

    row = conn.execute(
        text("""
            INSERT INTO enrollments (
                student_id,
                subject_id,
                section,
                teaching_assignment_id
            )
            VALUES (
                :student_id,
                :subject_id,
                :section,
                :assignment_id
            )
            RETURNING id
        """),
        {
            "student_id": student["id"],
            "subject_id": assignment["subject_id"],
            "section": assignment["section"],
            "assignment_id": assignment_id,
        },
    ).mappings().first()

    return {
        "enrollment_id": str(row["id"]),
        "student_id": str(student["id"]),
        "usn": student["usn"],
        "name": student["name"],
        "subject_id": str(assignment["subject_id"]),
        "teaching_assignment_id": assignment_id,
        "section": assignment["section"],
    }
