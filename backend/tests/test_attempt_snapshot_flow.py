from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.quizzes import (
    _questions_for_attempt,
    _mask_questions_for_student,
    review_attempt,
)


def _snapshot():
    return [{
        "id": "question-1",
        "module_id": "module-1",
        "co_id": "co-1",
        "co_number": 1,
        "stem": "Original question",
        "options": ["A", "B", "C", "D"],
        "correct_option": 2,
        "explanation": "Original explanation",
        "marks": 5,
    }]


def test_resume_uses_saved_question():
    store = MagicMock()
    store.get_attempt_question_snapshot.return_value = _snapshot()

    attempt = SimpleNamespace(
        id="attempt-1",
        quiz_id="quiz-1",
    )

    questions = _questions_for_attempt(store, attempt)

    assert questions[0].stem == "Original question"
    store.get_questions_for_quiz.assert_not_called()


def test_student_questions_hide_answer_key():
    store = MagicMock()
    store.get_attempt_question_snapshot.return_value = _snapshot()

    attempt = SimpleNamespace(
        id="attempt-1",
        quiz_id="quiz-1",
    )

    questions = _questions_for_attempt(store, attempt)
    visible = _mask_questions_for_student(questions)

    assert visible[0]["stem"] == "Original question"
    assert "correct_option" not in visible[0]
    assert "explanation" not in visible[0]


def test_review_uses_original_correct_answer():
    store = MagicMock()
    store.get_attempt.return_value = SimpleNamespace(
        id="attempt-1",
        quiz_id="quiz-1",
        student_id="student-1",
        answers={"question-1": 1},
        submitted_at=datetime.now(timezone.utc),
    )
    store.get_attempt_question_snapshot.return_value = _snapshot()

    result = review_attempt(
        store,
        {"role": "student", "student_id": "student-1"},
        "attempt-1",
    )

    assert result[0]["correct"] == 2
    assert result[0]["chosen"] == 1
    assert result[0]["explanation"] == "Original explanation"
    store.get_questions_for_quiz.assert_not_called()
