import secrets

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError
from ..pg.common import as_uuid
from ..security import hash_password
from ..services.student_import import parse_student_file

router = APIRouter(tags=["teaching-assignments"])


def get_class(conn, assignment_id, faculty_id):
    assignment_id = as_uuid(assignment_id, "Teaching assignment")
    row = conn.execute(
        text("""
            SELECT ta.*
            FROM teaching_assignments ta
            JOIN subjects s ON s.id = ta.subject_id
            WHERE ta.id = :id
              AND s.faculty_user_id = :faculty_id
        """),
        {"id": assignment_id, "faculty_id": faculty_id},
    ).mappings().first()

    if row is None:
        raise AppError(404, "NOT_FOUND", "Class not found")

    if row["status"] != "active":
        raise AppError(409, "CONFLICT", "Class is archived")

    return row


def read_upload(file):
    try:
        return parse_student_file(
            file.filename or "",
            file.file.read(5 * 1024 * 1024 + 1),
        )
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc


def analyze(conn, assignment, parsed):
    ready = []
    skipped = list(parsed["errors"])

    for student in parsed["valid"]:
        existing = conn.execute(
            text("""
                SELECT s.id, s.name, e.id AS enrollment_id
                FROM students s
                LEFT JOIN enrollments e
                  ON e.student_id = s.id
                 AND e.subject_id = :subject_id
                WHERE s.usn = :usn
            """),
            {
                "usn": student["usn"],
                "subject_id": assignment["subject_id"],
            },
        ).mappings().first()

        if existing and existing["enrollment_id"]:
            skipped.append({
                "row": student["row"],
                "usn": student["usn"],
                "reason": "Already enrolled in this subject",
            })
        elif existing and existing["name"].strip() != student["name"]:
            skipped.append({
                "row": student["row"],
                "usn": student["usn"],
                "reason": "Name differs from existing record",
            })
        else:
            ready.append(student)

    return ready, skipped


@router.post(
    "/teaching-assignments/{assignment_id}/students/bulk-preview"
)
def preview_students(
    assignment_id: str,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = get_class(conn, assignment_id, faculty["user_id"])
    parsed = read_upload(file)
    ready, skipped = analyze(conn, assignment, parsed)

    return {
        "total_rows": parsed["total_rows"],
        "ready_count": len(ready),
        "skipped_count": len(skipped),
        "ready": ready,
        "skipped": skipped,
    }


@router.post(
    "/teaching-assignments/{assignment_id}/students/bulk-upload"
)
def upload_students(
    assignment_id: str,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    assignment = get_class(conn, assignment_id, faculty["user_id"])
    parsed = read_upload(file)
    ready, skipped = analyze(conn, assignment, parsed)

    created_students = 0
    enrolled_students = 0
    credentials = []

    for student in ready:
        existing = conn.execute(
            text("SELECT id FROM students WHERE usn = :usn"),
            {"usn": student["usn"]},
        ).mappings().first()

        if existing:
            student_id = existing["id"]
        else:
            pin = str(secrets.randbelow(900000) + 100000)

            created = conn.execute(
                text("""
                    INSERT INTO students (usn, name, pin_hash)
                    VALUES (:usn, :name, :pin_hash)
                    ON CONFLICT (usn) DO NOTHING
                    RETURNING id
                """),
                {
                    "usn": student["usn"],
                    "name": student["name"],
                    "pin_hash": hash_password(pin),
                },
            ).mappings().first()

            if created:
                student_id = created["id"]

                conn.execute(
                    text("""
                        INSERT INTO users (role, student_id)
                        VALUES ('student', :student_id)
                    """),
                    {"student_id": student_id},
                )

                created_students += 1
                credentials.append({
                    "usn": student["usn"],
                    "pin": pin,
                })
            else:
                existing = conn.execute(
                    text("SELECT id, name FROM students WHERE usn = :usn"),
                    {"usn": student["usn"]},
                ).mappings().first()

                if existing is None or existing["name"].strip() != student["name"]:
                    skipped.append({
                        "row": student["row"],
                        "usn": student["usn"],
                        "reason": "Student record changed during import",
                    })
                    continue

                student_id = existing["id"]

        inserted = conn.execute(
            text("""
                INSERT INTO enrollments (
                    student_id, subject_id, section,
                    teaching_assignment_id
                )
                VALUES (
                    :student_id, :subject_id, :section,
                    :assignment_id
                )
                ON CONFLICT (student_id, subject_id) DO NOTHING
                RETURNING id
            """),
            {
                "student_id": student_id,
                "subject_id": assignment["subject_id"],
                "section": assignment["section"],
                "assignment_id": assignment["id"],
            },
        ).mappings().first()

        if inserted:
            enrolled_students += 1
        else:
            skipped.append({
                "row": student["row"],
                "usn": student["usn"],
                "reason": "Already enrolled in this subject",
            })

    return {
        "total_rows": parsed["total_rows"],
        "created_students": created_students,
        "enrolled_students": enrolled_students,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "credentials": credentials,
    }
