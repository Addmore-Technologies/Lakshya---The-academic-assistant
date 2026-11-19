import json
from types import SimpleNamespace

from ai import evaluate_models
from ai.model_evaluation import evaluate_quiz_generation, summarize_tag_runs



MODULE = {"id": "m", "title": "Searching", "slides": [{"slide_number": 7, "text": "Binary search halves the search space."}]}
COS = [{"id": "c1", "number": 1, "description": "Analyze search algorithms"}]


class QuizClient:
    def chat(self, **kwargs):
        question = {"stem": "What halves the search space?", "options": ["Binary search", "B", "C", "D"],
                    "correct_option": 0, "source_slide_number": 7, "source_quote": MODULE["slides"][0]["text"],
                    "co_number": 1, "co_confidence": 0.95}
        return SimpleNamespace(content=json.dumps({"questions": [question]}))

    def close(self):
        pass


def test_quiz_evaluation_includes_definitions_and_cited_evidence_for_review():
    report = evaluate_quiz_generation(MODULE, COS, "easy", 1, QuizClient(), model="test")
    assert report["course_outcomes"] == COS
    assert report["drafts"][0]["source_slide_number"] == 7
    assert report["drafts"][0]["co_id"] == "c1"


def test_quiz_cli_accepts_an_outcomes_file(tmp_path, monkeypatch):
    config = SimpleNamespace(create_client=QuizClient, model_for=lambda task: "test")
    monkeypatch.setattr(evaluate_models.AIConfig, "from_env", lambda: config)
    module_file, outcomes_file, report_file = [tmp_path / name for name in ("module.json", "cos.json", "report.json")]
    module_file.write_text(json.dumps(MODULE))
    outcomes_file.write_text(json.dumps(COS))
    assert evaluate_models.main(["quiz", "--module-json", str(module_file), "--cos-file", str(outcomes_file),
                                 "--count", "1", "--difficulty", "easy", "--output", str(report_file)]) == 0
    assert json.loads(report_file.read_text())["course_outcomes"] == COS


def test_tag_run_summary_reports_repeat_consistency_per_chunk():
    report = summarize_tag_runs(
        ["chunk-1", "chunk-2"],
        [
            [{"chunk_id": "chunk-1", "cos": [1]}, {"chunk_id": "chunk-2", "cos": [1]}],
            [{"chunk_id": "chunk-1", "cos": [1]}],
        ],
    )

    assert report["repeat_count"] == 2
    assert report["exact_agreement_rate"] == 0.5
    assert report["mean_pairwise_jaccard"] == 0.5
    assert report["by_chunk"]["chunk-1"]["exact_agreement"] is True
    assert report["by_chunk"]["chunk-2"]["exact_agreement"] is False


def test_tag_run_summary_handles_all_untagged_repeated_chunks():
    report = summarize_tag_runs(["chunk-1"], [[], []])

    assert report["by_chunk"]["chunk-1"]["tags_by_run"] == [[], []]
    assert report["by_chunk"]["chunk-1"]["exact_agreement"] is True
    assert report["mean_pairwise_jaccard"] == 1.0
