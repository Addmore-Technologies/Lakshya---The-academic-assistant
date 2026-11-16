"""Tests for legacy PPT conversion."""

import pytest

from backend.app.services.ppt_conversion import convert_ppt_to_pptx


def test_empty_ppt():
    with pytest.raises(ValueError, match="empty"):
        convert_ppt_to_pptx(b"")


def test_invalid_ppt():
    with pytest.raises(ValueError, match="Invalid legacy PPT"):
        convert_ppt_to_pptx(b"not a PowerPoint file")


def test_missing_libreoffice(monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("libreoffice")

    monkeypatch.setattr(
        "backend.app.services.ppt_conversion.subprocess.run",
        unavailable,
    )

    ppt_header = bytes.fromhex("D0CF11E0A1B11AE1")

    with pytest.raises(ValueError, match="LibreOffice is not installed"):
        convert_ppt_to_pptx(ppt_header + b"test data")
