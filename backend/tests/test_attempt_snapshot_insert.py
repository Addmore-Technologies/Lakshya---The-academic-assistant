import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.stores.postgres_quiz_store import PostgresQuizStore


def test_new_attempt_insert_includes_class_and_snapshot():
    conn = MagicMock()

    # No existing attempt, so save_attempt takes the INSERT path.
    conn.execute.return_value.mappings.return_value.fetchone.return_value = None

    store = PostgresQuizStore(conn)

    store._resolve_attempt_assignment = MagicMock(
        return_value="assignment-1"
    )
    store._create_question_snapshot = MagicMock(
        return_value=[
            {
                "id": "question-1",
                "stem": "Original question",
                "correct_option": 2,
            }
        ]
    )

    attempt = SimpleNamespace(
        id="attempt-1",
        quiz_id="quiz-1",
        student_id="student-1",
        attempt_number=1,
        answers={},
        total_score=None,
        max_score=None,
        started_at=datetime.now(timezone.utc),
        submitted_at=None,
    )

    store.save_attempt(attempt)

    assert conn.execute.call_count == 2

    insert_sql, insert_params = conn.execute.call_args.args

    assert "INSERT INTO quiz_attempts" in str(insert_sql)
    assert "teaching_assignment_id" in str(insert_sql)
    assert "question_snapshot" in str(insert_sql)

    assert insert_params["assignment_id"] == "assignment-1"

    snapshot = json.loads(insert_params["question_snapshot"])
    assert snapshot[0]["stem"] == "Original question"
    assert snapshot[0]["correct_option"] == 2


def test_updating_attempt_does_not_replace_snapshot():
    conn = MagicMock()

    conn.execute.return_value.mappings.return_value.fetchone.return_value = {
        "id": "attempt-1"
    }

    store = PostgresQuizStore(conn)

    attempt = SimpleNamespace(
        id="attempt-1",
        quiz_id="quiz-1",
        student_id="student-1",
        attempt_number=1,
        answers={"question-1": 2},
        total_score=5,
        max_score=5,
        started_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
    )

    store.save_attempt(attempt)

    update_sql, update_params = conn.execute.call_args.args

    assert "UPDATE quiz_attempts" in str(update_sql)
    assert "question_snapshot" not in str(update_sql)
    assert "teaching_assignment_id" not in str(update_sql)
    assert update_params["ts"] == 5
