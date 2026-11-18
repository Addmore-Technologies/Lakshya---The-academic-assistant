import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from app.errors import AppError
from app.routers.attempt_history import (
    _serialize,
    my_attempt_history,
    class_attempt_history,
)
from app.routers.subjects import list_cos
from app.routers.teaching_assignments import get_assignment_roster


def test_student_history_filters_by_authenticated_student():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    my_attempt_history(
        conn=conn,
        current_user={"role": "student", "student_id": "student-1"},
    )

    sql, params = conn.execute.call_args.args

    assert "qa.student_id = :student_id" in str(sql)
    assert params["student_id"] == "student-1"


def test_non_student_cannot_access_student_history():
    conn = MagicMock()

    with pytest.raises(AppError):
        my_attempt_history(
            conn=conn,
            current_user={"role": "faculty", "user_id": "faculty-1"},
        )

    conn.execute.assert_not_called()


def test_faculty_cannot_access_unowned_class_history():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(AppError):
        class_attempt_history(
            assignment_id="assignment-1",
            conn=conn,
            faculty={"user_id": "faculty-1"},
        )

    assert conn.execute.call_count == 1

    sql, params = conn.execute.call_args.args

    assert "sub.faculty_user_id = :faculty_id" in str(sql)
    assert params["faculty_id"] == "faculty-1"


def test_authorized_faculty_reads_only_selected_assignment_history():
    # Real SQLAlchemy results: a MagicMock supports string indexing on any result.
    engine = create_engine("sqlite://", connect_args={"detect_types": sqlite3.PARSE_DECLTYPES})
    with engine.connect() as conn:
        for statement in (
            "CREATE TABLE subjects(id, faculty_user_id, code, name, semester)",
            "CREATE TABLE teaching_assignments(id, subject_id, section, status)",
            "CREATE TABLE course_outcomes(id, subject_id, number, description, threshold_pct, target_attainment_pct)",
            "CREATE TABLE enrollments(student_id, subject_id, teaching_assignment_id, section, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE students(id, usn, name)",
            "CREATE TABLE quizzes(id, subject_id, title)",
            "CREATE TABLE quiz_attempts(id, quiz_id, student_id, teaching_assignment_id, "
            "attempt_number, total_score, max_score, started_at, submitted_at, answers)",
            "INSERT INTO subjects VALUES ('s', 'faculty-1','CS','Computing','1')",
            "INSERT INTO teaching_assignments VALUES ('a', 's', 'A', 'active'), ('b', 's', 'B', 'active')",
            "INSERT INTO students VALUES ('1','U1','First'), ('2','U2','Second')",
            "INSERT INTO enrollments(student_id,subject_id,teaching_assignment_id,section) "
            "VALUES ('1','s','a','A'), ('2','s','b','B')",
            "INSERT INTO quizzes VALUES ('q','s','Shared quiz')",
            "INSERT INTO quiz_attempts (id,quiz_id,student_id,teaching_assignment_id,attempt_number) "
            "VALUES ('attempt-a','q','1','a',1), ('attempt-b','q','2','b',1), ('legacy','q','1',NULL,2)",
        ):
            conn.exec_driver_sql(statement)
        conn.exec_driver_sql("INSERT INTO course_outcomes VALUES (?, 's', ?, ?, 60, 60)",
                             [(n, n, f'Outcome {n}') for n in range(1, 7)])
        faculty = {"user_id": "faculty-1"}
        for section, student in (("a", "1"), ("b", "2")):
            roster = get_assignment_roster(section, conn, faculty)
            assert [s["student_id"] for s in roster["students"]] == [student]
            subject_id = roster["teaching_assignment"]["subject_id"]
            assert [co["id"] for co in list_cos(subject_id, conn, faculty)] == list("123456")
            history = class_attempt_history(section, conn, faculty)
            assert [row["attempt_id"] for row in history] == [f"attempt-{section}"]
            assert history[0]["student_id"] == student
            assert history[0]["subject_id"] == "s"
            assert history[0]["teaching_assignment_id"] == section


def test_unsubmitted_history_hides_answers():
    row = {
        "attempt_id": "attempt-1",
        "quiz_id": "quiz-1",
        "quiz_title": "Quiz",
        "student_id": "student-1",
        "usn": "USN001",
        "student_name": "Student",
        "subject_id": "subject-1",
        "teaching_assignment_id": "assignment-1",
        "section": "A",
        "attempt_number": 1,
        "total_score": None,
        "max_score": None,
        "started_at": datetime.now(timezone.utc),
        "submitted_at": None,
        "answers": {"question-1": 2},
    }

    assert _serialize(row)["answers"] is None

    row["submitted_at"] = datetime.now(timezone.utc)

    assert _serialize(row)["answers"] == {"question-1": 2}
