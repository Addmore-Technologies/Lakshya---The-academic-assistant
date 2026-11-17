from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.errors import AppError
from app.routers.attempt_history import (
    _serialize,
    my_attempt_history,
    class_attempt_history,
)


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
    conn.execute.return_value.first.return_value = None

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
