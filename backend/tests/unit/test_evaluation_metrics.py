import hashlib
import json
from evaluation.metrics import aggregate, citation_marker_valid, keyword_group_score, score_case
import httpx

from evaluation.run import request_json, validate_dataset, verify_source_files


def test_answerable_case_scores_source_rank_keywords_and_citations():
    case = {"id": "one", "kind": "answerable", "expected_sources": ["课程.pdf"],
            "answer_key_groups": [["检索"], ["生成", "回答"]]}
    retrieval = [{"original_filename": "噪声.pdf"}, {"original_filename": "课程.pdf"}]
    answer = {"answer": "RAG 结合检索与生成 [1]", "citations": [
        {"reference": 1, "original_filename": "课程.pdf"},
        {"reference": 2, "original_filename": "噪声.pdf"},
    ]}
    score = score_case(case, retrieval, answer)
    assert score["retrieval_hit"] is True
    assert score["reciprocal_rank"] == 0.5
    assert score["answer_keyword_coverage"] == 1.0
    assert score["citation_source_precision"] == 0.5
    assert score["citation_source_hit"] is True
    assert score["citation_markers_valid"] is True


def test_unanswerable_case_requires_canonical_refusal_and_no_citations():
    case = {"id": "negative", "kind": "unanswerable", "expected_sources": [],
            "answer_key_groups": [["无法从当前知识库中确认"]]}
    score = score_case(case, [], {"answer": "无法从当前知识库中确认。", "citations": []})
    assert score["retrieval_empty"] is True
    assert score["refusal_correct"] is True
    assert score["citation_markers_valid"] is True
    assert score["citation_source_precision"] == 1.0


def test_keyword_groups_accept_alternatives_and_markers_reject_unknown_reference():
    assert keyword_group_score("使用 LLM 和外部资料", [["大模型", "LLM"], ["知识库", "外部资料"]]) == (2, 2, 1.0)
    assert citation_marker_valid("结论 [1][3]", [{"reference": 1}, {"reference": 2}]) is False


def test_aggregate_keeps_retrieval_and_generation_metrics_separate():
    scores = [
        {"kind":"answerable","retrieval_hit":True,"reciprocal_rank":1.0,"retrieval_empty":False,
         "answer_keyword_coverage":0.75,"citation_source_precision":1.0,"citation_source_hit":True,"citation_markers_valid":True},
        {"kind":"unanswerable","retrieval_hit":False,"reciprocal_rank":0.0,"retrieval_empty":True,
         "answer_keyword_coverage":1.0,"citation_source_precision":1.0,"citation_source_hit":False,"citation_markers_valid":True,"refusal_correct":True},
    ]
    summary = aggregate(scores, include_answers=True)
    assert summary["retrieval_hit_at_k"] == 1.0
    assert summary["answer_keyword_coverage"] == 0.75
    assert summary["refusal_accuracy"] == 1.0


def test_evaluation_retries_transient_http_failure(monkeypatch):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            503 if attempts == 1 else 200,
            request=request,
            json={"status": "ok"},
        )

    monkeypatch.setattr("evaluation.run.time.sleep", lambda delay: None)
    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = request_json(client, "POST", "/answer", json={})

    assert attempts == 2
    assert result == {"status": "ok"}


def test_bundled_dataset_is_valid_and_balanced():
    from pathlib import Path
    path = Path(__file__).parents[2] / "evaluation" / "langchain_baseline.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    assert len(dataset["source_documents"]) == 10
    assert sum(case["kind"] == "answerable" for case in dataset["cases"]) == 20
    assert sum(case["kind"] == "unanswerable" for case in dataset["cases"]) == 3


def test_dataset_validation_supports_a_different_corpus_size(tmp_path):
    source = tmp_path / "docs" / "guide.md"
    source.parent.mkdir()
    source.write_text("跨领域评测", encoding="utf-8")
    dataset = {
        "version": 1,
        "name": "other-kb",
        "source_documents": [{
            "filename": "guide.md",
            "source_path": "docs/guide.md",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }],
        "cases": [{
            "id": "answerable", "kind": "answerable",
            "question": "评测什么？", "expected_sources": ["guide.md"],
            "answer_key_groups": [["跨领域"]],
        }],
    }

    validate_dataset(dataset)
    verify_source_files(dataset, tmp_path)
