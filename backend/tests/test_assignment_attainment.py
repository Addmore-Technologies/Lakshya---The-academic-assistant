"""Exercise the route and its real SQL against a private, in-memory database."""
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

SUBJECT, A, B = (str(UUID(int=i)) for i in (1, 2, 3))


@pytest.fixture
def api(monkeypatch):
    # Route imports require config even though DB and identity are overridden.
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')
    monkeypatch.setenv('SESSION_SECRET', 'unused')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '1')
    from app.db import get_conn
    from app.deps import get_current_user
    from app.errors import AppError, app_error_handler
    from app.routers.teaching_assignments import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        sql = conn.exec_driver_sql
        for schema in (
            "subjects (id, code, name, semester, faculty_user_id)",
            "teaching_assignments (id, subject_id, section, status)",
            "course_outcomes (id, subject_id, number, description, threshold_pct, target_attainment_pct)",
            "students (id, usn, name)",
            "enrollments (student_id, subject_id, section, teaching_assignment_id)",
            "quizzes (id, subject_id, module_id)",
            "quiz_attempts (id, quiz_id, student_id, teaching_assignment_id, attempt_number, answers, submitted_at)",
            "student_co_scores (attempt_id, student_id, subject_id, module_id, co_id, marks_obtained, max_marks)",
        ):
            sql(f"CREATE TABLE {schema}")
        sql("INSERT INTO subjects VALUES (?, 'CS', 'Computing', 1, 'owner')", (SUBJECT,))
        sql("INSERT INTO teaching_assignments VALUES (?, ?, ?, 'active')", [(A, SUBJECT, 'A'), (B, SUBJECT, 'B')])
        for n in range(1, 7):
            sql("INSERT INTO course_outcomes VALUES (?, ?, ?, ?, 70, 60)", (n, SUBJECT, n, f"Outcome {n}"))
        for student, section, assignment in [('a1', 'A', A), ('a2', 'A', A), ('b1', 'B', B), ('old', 'A', None)]:
            sql("INSERT INTO students VALUES (?, ?, ?)", (student, student, student))
            sql("INSERT INTO enrollments VALUES (?, ?, ?, ?)", (student, SUBJECT, section, assignment))

        def score(quiz, student, assignment, marks, attempt=1, submitted=True):
            aid = f"{quiz}-{student}-{attempt}"
            sql("INSERT INTO quiz_attempts VALUES (?, ?, ?, ?, ?, '{}', ?)",
                (aid, quiz, student, assignment, attempt, 'submitted' if submitted else None))
            for n, mark in enumerate(marks, 1):
                sql("INSERT INTO student_co_scores VALUES (?, ?, ?, 'module', ?, ?, 10)", (aid, student, SUBJECT, n, mark))

        for quiz in ('shared', 'prior', 'legacy', 'unfinished'):
            sql("INSERT INTO quizzes VALUES (?, ?, 'module')", (quiz, SUBJECT))
        score('shared', 'a1', A, [7, 0, 10, 0, 10])
        score('shared', 'a1', A, [0, 1, 0, 1, 0], attempt=2)
        score('shared', 'b1', B, [0, 8, 0, 8, 0, 8])
        # Same current student, but these scores must not follow them into A.
        score('prior', 'a1', B, [10] * 6)
        score('legacy', 'a1', None, [10] * 6)
        score('unfinished', 'a1', A, [10] * 6, submitted=False)

        app = FastAPI()
        app.include_router(router)
        app.add_exception_handler(AppError, app_error_handler)
        user = {'role': 'faculty', 'user_id': 'owner'}
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_conn] = lambda: conn
        with TestClient(app) as client:
            yield client, user


def test_sections_share_definitions_but_not_attainment(api, monkeypatch):
    client, _ = api
    monkeypatch.setenv('ATTEMPT_RULE', 'best')
    for assignment, expected in [(A, [50, 0, 50, 0, 50, None]), (B, [0, 100, 0, 100, 0, 100])]:
        response = client.get(f'/teaching-assignments/{assignment}/attainment')
        assert response.status_code == 200
        data = response.json()
        assert data['subject_id'] == SUBJECT
        assert data['teaching_assignment_id'] == assignment
        assert [(co['number'], co['description'], co['attainment_pct']) for co in data['cos']] == [
            (n, f'Outcome {n}', pct) for n, pct in enumerate(expected, 1)
        ]


def test_configured_attempt_rule(api, monkeypatch):
    client, _ = api
    monkeypatch.setenv('ATTEMPT_RULE', 'latest')
    response = client.get(f'/teaching-assignments/{A}/attainment')
    assert response.status_code == 200
    assert [co['attainment_pct'] for co in response.json()['cos']] == [0, 0, 0, 0, 0, None]


@pytest.mark.parametrize(('role', 'user_id', 'status'), [('faculty', 'other', 404), ('student', 'owner', 403)])
def test_only_owning_faculty_can_read(api, role, user_id, status):
    client, user = api
    user.update(role=role, user_id=user_id)
    response = client.get(f'/teaching-assignments/{A}/attainment')
    assert response.status_code == status
    assert response.json()['error']['code'] == ('NOT_FOUND' if status == 404 else 'FORBIDDEN')
