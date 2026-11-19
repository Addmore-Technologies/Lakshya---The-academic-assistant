"""Local evidence for a quiz-deck review; lack of keyword overlap is not a mismatch."""
import re


# Use specific concepts rather than isolated words like 'test', 'data' or 'plan'.
# Group spelling variants of a concept so repeats alone cannot trigger review.
_TOPICS = (
    (r"databases?|dbms|rdbms", r"query optimi[sz](?:ation|er)", r"sql",
     r"query plans?|execution plans?", r"join ordering|join algorithms?", r"relational algebra"),
    (r"software testing", r"test cases?", r"regression test(?:ing|s)?", r"unit test(?:ing|s)?",
     r"integration test(?:ing|s)?", r"black box|white box", r"defect tracking",
     r"verification and validation", r"equivalence partitioning", r"boundary value analysis"),
)


def _matches(terms, value):
    words = re.sub(r"[\W_]+", " ", value.casefold())
    return {term for term in terms if re.search(rf"\b(?:{term})\b", words)}


def suspect_deck(title, subject, slides):
    """Require a known expected topic and independent evidence of a different one."""
    expected = [terms for terms in _TOPICS if _matches(terms, title + " " + subject)]
    if not expected:
        return False
    for terms in _TOPICS:
        if terms in expected:
            continue
        hits = [_matches(terms, slide["text"]) for slide in slides]
        if len(set().union(*hits)) >= 2 and sum(bool(h) for h in hits) > len(slides) / 2:
            return True
    return False
