from pathlib import Path

from backend.app.services.co_extraction import (
    extract_cos_from_pdf,
    extract_cos_from_text,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "5_CESE_Agile_Software_Development_23CSE504.pdf"
)


def test_agile_syllabus_extracts_six_valid_cos():
    results = extract_cos_from_pdf(FIXTURE.read_bytes())

    assert [co["number"] for co in results] == [1, 2, 3, 4, 5, 6]

    assert [co["bloom_level"] for co in results] == [
        2, 2, 3, 3, 3, 4
    ]

    expected_phrases = [
        "Outline the principles",
        "Understand the benefits",
        "Demonstrate the Agile Approaches",
        "Examine the process",
        "Illustrate the management skills",
        "Recommend the various metrics",
    ]

    for co, phrase in zip(results, expected_phrases):
        assert phrase in co["description"]
        assert len(co["description"]) >= 25


def test_numeric_co_mapping_is_not_extracted():
    text = """
    CO-PO/PSO Mapping:
    CO1 2 2 1 2 3
    CO2 2 2 2 1 2 3
    CO3 3 2 2 2 1 2
    """

    assert extract_cos_from_text(text) == []


def test_multiline_course_outcome():
    text = """
    Course Outcomes:
    1. CO 1 Explain Agile principles
    and software development practices.
    Understanding (2)
    CO-PO/PSO Mapping:
    CO1 2 2 1 2 3
    """

    results = extract_cos_from_text(text)

    assert len(results) == 1
    assert results[0]["number"] == 1
    assert "software development practices" in results[0]["description"]
    assert results[0]["bloom_level"] == 2
