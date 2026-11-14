"""Unit tests for module extraction and AI tagging statuses."""

import uuid
from unittest.mock import MagicMock

import pytest

from backend.app.pg.chunks import module_status


@pytest.mark.parametrize(
    "total,tagged,error,expected",
    [
        (5, 0, "AI_NOT_CONFIGURED: Missing credentials", "ai_not_configured"),
        (5, 0, "AI request failed", "failed"),
        (5, 2, "AI request failed", "partial"),
        (5, 5, None, "completed"),
    ],
)
def test_module_tagging_status(total, tagged, error, expected):
    conn = MagicMock()

    conn.execute.return_value.mappings.return_value.fetchone.return_value = {
        "processing_status": "done",
        "processing_error": error,
        "total": total,
        "tagged": tagged,
    }

    result = module_status(conn, str(uuid.uuid4()))

    assert result["processing_status"] == "done"
    assert result["extraction_status"] == "completed"
    assert result["tagging_status"] == expected
    assert result["tagging_error"] == error
    assert result["chunks_total"] == total
    assert result["chunks_tagged"] == tagged
    assert result["chunks_untagged"] == total - tagged


def test_module_status_not_found():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.fetchone.return_value = None

    assert module_status(conn, str(uuid.uuid4())) is None
