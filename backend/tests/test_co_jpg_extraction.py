"""Tests for JPG course outcome extraction."""

import io

import pytest
import pytesseract

from PIL import Image
from backend.app.services.co_extraction import extract_cos_from_jpg


def make_jpg():
    image = Image.new("RGB", (800, 400), "white")
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def test_extract_cos_from_jpg(monkeypatch):
    ocr_text = (
        "Course Outcomes:\n"
        "CO1: Explain the principles of agile software development\n"
        "CO2: Apply iterative development techniques in projects\n"
    )

    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda *args, **kwargs: ocr_text,
    )

    cos = extract_cos_from_jpg(make_jpg())

    assert len(cos) == 2
    assert cos[0]["number"] == 1
    assert cos[1]["number"] == 2


def test_missing_ocr_engine(monkeypatch):
    def missing_engine(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        missing_engine,
    )

    with pytest.raises(ValueError, match="OCR engine"):
        extract_cos_from_jpg(make_jpg())


def test_invalid_jpg():
    with pytest.raises(ValueError, match="Could not read"):
        extract_cos_from_jpg(b"not-an-image")
