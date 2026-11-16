"""Tests for course outcome extraction from PowerPoint."""

import io

from pptx import Presentation

from backend.app.services.co_extraction import extract_cos_from_pptx


def test_extract_cos_from_pptx():
    prs = Presentation()

    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Course Outcomes:"
    slide.placeholders[1].text = (
        "CO1: Explain the principles of agile software development\n"
        "CO2: Apply iterative development techniques in projects"
    )

    output = io.BytesIO()
    prs.save(output)

    cos = extract_cos_from_pptx(output.getvalue())

    assert len(cos) == 2
    assert cos[0]["number"] == 1
    assert cos[1]["number"] == 2
    assert "agile" in cos[0]["description"].lower()
