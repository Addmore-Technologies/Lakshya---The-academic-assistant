from app.services.co_extraction import extract_cos_from_text


def test_single_line_cos():
    text = """
    CO1: Explain Agile principles.
    CO2: Apply Scrum practices.
    CO3: Analyze project requirements.
    """
    cos = extract_cos_from_text(text)

    assert len(cos) == 3
    assert cos[0]["description"] == "Explain Agile principles."
    assert cos[1]["number"] == 2


def test_multiline_cos():
    text = """
CO1 Explain the principles
of Agile software development.

CO2 Apply Scrum practices
in software projects.
"""
    cos = extract_cos_from_text(text)

    assert len(cos) == 2
    assert cos[0]["description"] == (
        "Explain the principles of Agile software development."
    )
    assert cos[1]["description"] == (
        "Apply Scrum practices in software projects."
    )


def test_duplicate_cos():
    text = """
CO1: Explain Agile principles.
CO1: Explain Agile principles.
CO2: Apply Scrum practices.
"""
    cos = extract_cos_from_text(text)

    assert len(cos) == 2
    assert [co["number"] for co in cos] == [1, 2]


def test_stops_at_module_heading():
    text = """
CO6 Recommend quality metrics.
MODULE I
Introduction to Agile
"""
    cos = extract_cos_from_text(text)

    assert len(cos) == 1
    assert cos[0]["description"] == "Recommend quality metrics."
