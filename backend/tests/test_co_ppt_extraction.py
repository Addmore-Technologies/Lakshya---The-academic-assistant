"""Tests for extracting course outcomes from legacy PPT files."""

import io

from pptx import Presentation

from backend.app.services import co_extraction


def test_extract_cos_from_legacy_ppt(monkeypatch):
    presentation = Presentation()
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[5]
    )

    textbox = slide.shapes.add_textbox(
        100000, 100000, 8000000, 2000000
    )

    textbox.text = (
        "Course Outcomes:\n"
        "CO1: Explain agile software development principles\n"
        "CO2: Apply iterative development techniques"
    )

    output = io.BytesIO()
    presentation.save(output)

    monkeypatch.setattr(
        "backend.app.services.ppt_conversion.convert_ppt_to_pptx",
        lambda file_bytes: output.getvalue(),
    )

    results = co_extraction.extract_cos_from_ppt(
        bytes.fromhex("D0CF11E0A1B11AE1") + b"test"
    )

    assert len(results) == 2
    assert results[0]["number"] == 1
    assert results[1]["number"] == 2
