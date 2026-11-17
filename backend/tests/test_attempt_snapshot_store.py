import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.stores.postgres_quiz_store import PostgresQuizStore


def test_snapshot_captures_original_question_data():
    store = PostgresQuizStore(MagicMock())

    question = SimpleNamespace(
        id="question-1",
        module_id="module-1",
        co_id="co-1",
        co_number=1,
        stem="Original question",
        options=["A", "B", "C", "D"],
        correct_option=2,
        marks=5,
    )

    store.get_questions_for_quiz = MagicMock(return_value=[question])

    snapshot = store._create_question_snapshot("quiz-1")

    assert len(snapshot) == 1
    assert snapshot[0]["stem"] == "Original question"
    assert snapshot[0]["correct_option"] == 2
    assert snapshot[0]["marks"] == 5

    question.stem = "Changed question"
    question.correct_option = 1

    assert snapshot[0]["stem"] == "Original question"
    assert snapshot[0]["correct_option"] == 2


def test_snapshot_reader_supports_legacy_null():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "question_snapshot": None
    }

    store = PostgresQuizStore(conn)

    assert store.get_attempt_question_snapshot("attempt-1") is None


def test_snapshot_reader_parses_json():
    conn = MagicMock()

    original = [
        {
            "id": "question-1",
            "stem": "Original",
            "correct_option": 2,
        }
    ]

    conn.execute.return_value.mappings.return_value.first.return_value = {
        "question_snapshot": json.dumps(original)
    }

    store = PostgresQuizStore(conn)

    assert store.get_attempt_question_snapshot("attempt-1") == original
