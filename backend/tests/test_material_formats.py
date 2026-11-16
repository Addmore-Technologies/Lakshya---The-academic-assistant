"""Verify supported study-material parsers."""

import io

from pptx import Presentation
from pypdf import PdfWriter

from backend.app.pipeline.ppt import parse_pptx
from backend.app.pipeline.pdf import parse_pdf


def test_pptx_material():
    presentation = Presentation()
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )
    slide.shapes.title.text = "Introduction to Agile"
    slide.placeholders[1].text = "Software development methods"

    output = io.BytesIO()
    presentation.save(output)
    output.seek(0)

    result = parse_pptx(output)

    assert result.total_slides == 1
    assert "Introduction to Agile" in result.chunks[0].text


def test_pdf_material():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    result = parse_pdf(output)

    assert result.total_slides == 1
    assert result.skipped_slides == (1,)
    assert result.chunks == ()
