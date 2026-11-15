from unittest.mock import MagicMock

from app.routers import subjects


def test_save_co_with_bloom(monkeypatch):
    monkeypatch.setattr(
        subjects, "_subject_owned", lambda *args: None
    )

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.fetchone.return_value = {
        "id": "co-test-id",
        "subject_id": "subject-test-id",
        "number": 1,
        "description": "Apply Agile practices.",
        "bloom_level": 3,
        "bloom_name": "Applying",
        "threshold_pct": 60,
        "target_attainment_pct": 60,
    }

    result = subjects.upsert_cos(
        id="subject-test-id",
        conn=conn,
        faculty={"user_id": "faculty-test-id"},
        payload={
            "cos": [{
                "number": 1,
                "description": "Apply Agile practices.",
                "bloom_level": 3,
            }]
        },
    )

    params = conn.execute.call_args.args[1]

    assert params["bloom_level"] == 3
    assert params["bloom_name"] == "Applying"
    assert result[0]["bloom_level"] == 3
    assert result[0]["bloom_name"] == "Applying"


def test_legacy_co_preserves_bloom(monkeypatch):
    monkeypatch.setattr(
        subjects, "_subject_owned", lambda *args: None
    )

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.fetchone.return_value = {
        "id": "co-test-id",
        "subject_id": "subject-test-id",
        "number": 1,
        "description": "Updated description.",
        "bloom_level": 3,
        "bloom_name": "Applying",
        "threshold_pct": 60,
        "target_attainment_pct": 60,
    }

    subjects.upsert_cos(
        id="subject-test-id",
        conn=conn,
        faculty={"user_id": "faculty-test-id"},
        payload={
            "cos": [{
                "number": 1,
                "description": "Updated description.",
            }]
        },
    )

    statement, params = conn.execute.call_args.args

    assert params["bloom_level"] is None
    assert params["bloom_name"] is None
    assert "COALESCE(EXCLUDED.bloom_level" in str(statement)
    assert "COALESCE(EXCLUDED.bloom_name" in str(statement)
