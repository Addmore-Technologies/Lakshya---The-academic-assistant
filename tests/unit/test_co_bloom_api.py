from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_conn
from app.deps import require_faculty
from app.routers import subjects


def test_faculty_save_and_retrieve_bloom(monkeypatch):
    stored = {}

    def fake_owned(conn, subject_id, faculty_id):
        assert subject_id == "test-subject"
        assert faculty_id == "test-faculty"

    monkeypatch.setattr(subjects, "_subject_owned", fake_owned)

    conn = MagicMock()

    def execute(statement, params):
        sql = str(statement)
        result = MagicMock()

        if "INSERT INTO course_outcomes" in sql:
            stored.update({
                "id": "test-co",
                "subject_id": params["sid"],
                "number": params["num"],
                "description": params["desc"],
                "bloom_level": params["bloom_level"],
                "bloom_name": params["bloom_name"],
                "threshold_pct": params["thresh"],
                "target_attainment_pct": params["target"],
            })
            result.mappings.return_value.fetchone.return_value = stored.copy()

        elif "SELECT * FROM course_outcomes" in sql:
            result.mappings.return_value.fetchall.return_value = [
                stored.copy()
            ]

        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

        return result

    conn.execute.side_effect = execute

    def fake_conn():
        yield conn

    app.dependency_overrides[get_conn] = fake_conn
    app.dependency_overrides[require_faculty] = lambda: {
        "user_id": "test-faculty",
        "role": "faculty",
    }

    try:
        with TestClient(app) as client:
            response = client.put(
                "/subjects/test-subject/cos",
                json={
                    "cos": [{
                        "number": 1,
                        "description": "Apply Agile practices",
                        "bloom_level": 3,
                    }]
                },
            )

            assert response.status_code == 200, response.text
            assert response.json()[0]["bloom_level"] == 3
            assert response.json()[0]["bloom_name"] == "Applying"

            response = client.get("/subjects/test-subject/cos")

            assert response.status_code == 200, response.text
            assert response.json()[0]["bloom_level"] == 3
            assert response.json()[0]["bloom_name"] == "Applying"

    finally:
        app.dependency_overrides.pop(get_conn, None)
        app.dependency_overrides.pop(require_faculty, None)


def test_student_cannot_save_cos():
    def reject_student():
        from app.errors import AppError
        raise AppError(403, "FORBIDDEN", "Faculty access required")

    def fake_conn():
        yield MagicMock()

    app.dependency_overrides[get_conn] = fake_conn
    app.dependency_overrides[require_faculty] = reject_student

    try:
        with TestClient(app) as client:
            response = client.put(
                "/subjects/test-subject/cos",
                json={
                    "cos": [{
                        "number": 1,
                        "description": "Test CO",
                        "bloom_level": 3,
                    }]
                },
            )

            assert response.status_code == 403, response.text

    finally:
        app.dependency_overrides.pop(get_conn, None)
        app.dependency_overrides.pop(require_faculty, None)


def test_real_faculty_role_check_rejects_student():
    from app.deps import get_current_user

    def fake_conn():
        yield MagicMock()

    app.dependency_overrides[get_conn] = fake_conn
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-student",
        "role": "student",
    }

    try:
        with TestClient(app) as client:
            response = client.put(
                "/subjects/test-subject/cos",
                json={
                    "cos": [{
                        "number": 1,
                        "description": "Test CO",
                        "bloom_level": 3,
                    }]
                },
            )

            assert response.status_code == 403, response.text
            assert response.json()["error"]["code"] == "FORBIDDEN"

    finally:
        app.dependency_overrides.pop(get_conn, None)
        app.dependency_overrides.pop(get_current_user, None)
