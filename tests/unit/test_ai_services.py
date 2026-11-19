from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ai.token_factory import TokenFactoryClient, TokenFactoryError
from ai.tagging import tag_content_with_COs
from ai.quiz_generation import generate_quiz, QuizGenerationError


class FakeClient:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def chat(self, *, model, messages, tools=None, tool_choice=None, **kwargs):
        self.calls.append({"model": model, "messages": messages, "tools": tools, **kwargs})
        value = self.contents.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(content=value, tool_calls=[], usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10})


def test_token_factory_client_sends_openai_compatible_request_and_returns_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello", "tool_calls": []}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        })

    client = TokenFactoryClient(
        api_key="x",
        base_url="https://factory.example/v1",
        transport=httpx.MockTransport(handler),
    )
    result = client.chat(model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert result.content == "hello"
    assert result.usage == {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
    assert seen["url"] == "https://factory.example/v1/chat/completions"
    assert seen["authorization"] == "Bearer x"
    assert seen["body"]["model"] == "test-model"


def test_token_factory_rejects_https_url_with_embedded_credentials():
    with pytest.raises(ValueError, match="HTTPS URL"):
        TokenFactoryClient(
            api_key="x",
            base_url="https://user:password@factory.example/v1",
        )


def test_tagging_batches_chunks_and_records_usage():
    chunks = [
        {"id": "a", "text": "Sorting algorithms"},
        {"id": "b", "text": "Binary search"},
        {"id": "c", "text": "Graph traversal"},
    ]
    client = FakeClient([
        '{"tags":[{"chunk_id":"a","cos":[1],"confidence":0.9},{"chunk_id":"b","cos":[2],"confidence":0.8}]}',
        '{"tags":[{"chunk_id":"c","cos":[1,2],"confidence":0.7}]}',
    ])
    usage = []

    result = tag_content_with_COs(
        chunks,
        [{"number": 1, "description": "Algorithms"}, {"number": 2, "description": "Searching"}],
        client,
        model="nano-test",
        batch_size=2,
        usage_recorder=usage.append,
    )

    assert result == [
        {"chunk_id": "a", "cos": [1], "confidence": 0.9},
        {"chunk_id": "b", "cos": [2], "confidence": 0.8},
        {"chunk_id": "c", "cos": [1, 2], "confidence": 0.7},
    ]
    assert len(client.calls) == 2
    assert len(usage) == 2
    assert all(item["model"] == "nano-test" for item in usage)


def test_tagging_retries_bad_json_once_then_leaves_chunk_untagged():
    client = FakeClient(["not json", "still not json"])
    usage = []

    result = tag_content_with_COs(
        [{"id": "a", "text": "Topic"}],
        [{"number": 1, "description": "CO 1"}],
        client,
        model="nano-test",
        usage_recorder=usage.append,
    )

    assert result == []
    assert len(client.calls) == 2
    assert len(usage) == 2
    assert all(entry["total_tokens"] == 10 for entry in usage)
    assert all(entry["error"] for entry in usage)


SLIDE_MODULE = {"id": "module-1", "title": "Algorithms", "slides": [
    {"slide_number": 3, "text": "Merge sort is a stable sorting algorithm."},
    {"slide_number": 8, "text": "Binary search requires sorted input."},
]}
OUTCOMES = [
    {"id": "co-2", "number": 2, "description": "Analyze sorting algorithms"},
    {"id": "co-4", "number": 4, "description": "Apply binary search"},
    {"id": "co-5", "number": 5, "description": "Build automata"},
]
SORT_QUESTION = {
    "stem": "Which sorting algorithm is stable?",
    "options": ["Merge sort", "Quick sort", "Heap sort", "Selection sort"],
    "correct_option": 0, "co_number": 2, "co_confidence": 0.95,
    "source_slide_number": 3, "source_quote": "Merge sort is a stable sorting algorithm.",
}
SEARCH_QUESTION = {
    "stem": "What does binary search require?",
    "options": ["A linked list", "Sorted input", "A queue", "A hash table"],
    "correct_option": 1, "co_number": 4, "co_confidence": 0.97,
    "source_slide_number": 8, "source_quote": "Binary search requires sorted input.",
}


def generate(questions, *, module=SLIDE_MODULE, outcomes=OUTCOMES):
    client = FakeClient([json.dumps({"questions": questions})])
    drafts = generate_quiz(module, course_outcomes=outcomes, difficulty="medium",
                           count=len(questions), client=client, model="super-test")
    return drafts, json.loads(client.calls[0]["messages"][-1]["content"])


def test_quiz_generation_maps_each_draft_using_all_candidate_definitions():
    drafts, prompt = generate([SORT_QUESTION, SEARCH_QUESTION])
    assert prompt["module"] == SLIDE_MODULE
    assert [(co["number"], co["description"]) for co in prompt["course_outcomes"]] == [
        (co["number"], co["description"]) for co in OUTCOMES
    ]
    assert [(d["co_id"], d["co_number"]) for d in drafts] == [("co-2", 2), ("co-4", 4)]
    for draft, question in zip(drafts, [SORT_QUESTION, SEARCH_QUESTION]):
        assert (draft["status"], draft["source"], draft["module_id"]) == ("draft", "AI", "module-1")
        assert draft["correct_option"] == question["correct_option"]
        assert draft["source_quote"] == question["source_quote"]
        assert draft["source_slide_number"] == question["source_slide_number"]


@pytest.mark.parametrize("bad_evidence", [
    {"source_slide_number": 1}, {"source_slide_number": True}, {"source_slide_number": 3.0},
    {"source_slide_number": 8}, {"source_quote": "Made-up quotation"},
    {"source_quote": " "}, {"source_quote": None},
    {"source_quote": "a stable sorting algorithm"},  # real quote, but omits the answer
    {"stem": "Which planet orbits the sun?"},  # unrelated stem attached to a real quote
])
def test_ungrounded_question_fails_entire_batch(bad_evidence):
    with pytest.raises(QuizGenerationError, match="Question 2.*evidence"):
        generate([SEARCH_QUESTION, {**SORT_QUESTION, **bad_evidence}])


def test_importers_can_use_the_same_evidence_gate_without_inference():
    from ai.quiz_generation import validate_slide_evidence

    slides = {3: SORT_QUESTION["source_quote"]}
    validate_slide_evidence(SORT_QUESTION, 1, slides, SORT_QUESTION["stem"], "Merge sort")
    with pytest.raises(QuizGenerationError, match="Question 2.*evidence"):
        validate_slide_evidence(SORT_QUESTION, 2, slides, SORT_QUESTION["stem"], "Quick sort")


@pytest.mark.parametrize("proposal", [
    {"co_number": None}, {"co_number": 99}, {"co_number": True}, {"co_number": 2.0},
    {"co_number": []}, {"co_number": 5},  # a real candidate, unrelated to the evidence
    {"co_confidence": 0.79}, {"co_confidence": True}, {"co_confidence": 1.1},
    {"co_confidence": None}, {"co_confidence": "high"},
])
def test_uncertain_or_unsupported_proposal_abstains_without_discarding_question(proposal):
    drafts, _ = generate([{**SORT_QUESTION, **proposal, "co_id": "untrusted"}])
    assert (drafts[0]["co_id"], drafts[0]["co_number"], drafts[0]["status"]) == (None, None, "draft")


def test_no_candidate_outcomes_still_allows_grounded_drafts():
    drafts, _ = generate([SORT_QUESTION], outcomes=[])
    assert (drafts[0]["co_id"], drafts[0]["co_number"]) == (None, None)


def test_shared_topic_alone_does_not_justify_a_specific_outcome():
    outcomes = [
        {"id": "co-1", "number": 1, "description": "Analyze sorting stability"},
        {"id": "co-2", "number": 2, "description": "Evaluate sorting complexity"},
    ]
    # The model proposes complexity, but its only evidence for that CO is
    # 'sorting', which fits the competing definition equally well.
    drafts, _ = generate([SORT_QUESTION], outcomes=outcomes)
    assert drafts[0]["co_id"] is None


@pytest.mark.parametrize("overrides", [
    {"module": {**SLIDE_MODULE, "slides": []}},
    {"module": {**SLIDE_MODULE, "slides": [SLIDE_MODULE["slides"][0]] * 2}},
    {"module": {**SLIDE_MODULE, "slides": [{"slide_number": True, "text": "Some text"}]}},
    {"module": {**SLIDE_MODULE, "slides": [{"slide_number": 1, "text": "  "}]}},
    {"course_outcomes": OUTCOMES[0]}, {"course_outcomes": [OUTCOMES[0], dict(OUTCOMES[0], id="c")]},
    {"course_outcomes": [dict(OUTCOMES[0], id="")]}, {"course_outcomes": [dict(OUTCOMES[0], number=True)]},
    {"count": 21}, {"count": True}, {"difficulty": "unsupported"},
])
def test_invalid_context_is_rejected_before_calling_model(overrides):
    client = FakeClient([])
    args = dict(module=SLIDE_MODULE, course_outcomes=OUTCOMES, count=1, difficulty="medium")
    with pytest.raises(ValueError):
        generate_quiz(**{**args, **overrides}, client=client, model="test")
    assert not client.calls


def test_quiz_generation_rejects_duplicate_stems():
    with pytest.raises(QuizGenerationError, match="duplicate"):
        generate([SORT_QUESTION, SORT_QUESTION])


@pytest.mark.parametrize("reported_difficulty", ["hard", ["medium"], {"level": "medium"}])
def test_quiz_generation_rejects_invalid_or_mismatched_difficulty(reported_difficulty):
    with pytest.raises(QuizGenerationError, match="difficulty"):
        generate([{**SORT_QUESTION, "difficulty": reported_difficulty}])


def test_token_factory_client_rejects_non_object_message():
    client = TokenFactoryClient(
        api_key="x",
        base_url="https://factory.example/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [{"message": "malformed"}]})
        ),
    )

    with pytest.raises(TokenFactoryError, match="unexpected shape"):
        client.chat(model="test-model", messages=[{"role": "user", "content": "hi"}])
    client.close()


def test_token_factory_client_rejects_plaintext_http_base_url():
    with pytest.raises(ValueError, match="HTTPS"):
        TokenFactoryClient(api_key="x", base_url="http://factory.example/v1")


def test_quiz_schema_matches_runtime_marks_and_option_validation():
    schema_path = Path(__file__).resolve().parents[2] / "ai" / "schemas" / "quiz-drafts.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    question = schema["properties"]["questions"]["items"]["properties"]

    required = set(schema["properties"]["questions"]["items"]["required"])
    assert {"co_number", "co_confidence", "source_slide_number", "source_quote"} <= required
    assert question["co_number"]["type"] == ["integer", "null"]
    assert question["source_slide_number"] == {"type": "integer", "minimum": 1}
    assert question["source_quote"]["minLength"] == 1
    assert (question["co_confidence"]["minimum"], question["co_confidence"]["maximum"]) == (0, 1)
    assert question["marks"]["type"] == "number"
    assert question["options"]["uniqueItems"] is True
