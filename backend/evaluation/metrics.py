import re
import unicodedata


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace(" ", "")


def first_expected_rank(results: list[dict], expected_sources: list[str]) -> int | None:
    expected = {normalize(item) for item in expected_sources}
    for index, result in enumerate(results, start=1):
        if normalize(result.get("original_filename", "")) in expected:
            return index
    return None


def keyword_group_score(answer: str, groups: list[list[str]]) -> tuple[int, int, float]:
    normalized = normalize(answer)
    matched = sum(any(normalize(term) in normalized for term in group) for group in groups)
    total = len(groups)
    return matched, total, matched / total if total else 1.0


def citation_marker_valid(answer: str, citations: list[dict]) -> bool:
    markers = {int(item) for item in re.findall(r"\[(\d+)\]", answer)}
    references = {int(item["reference"]) for item in citations}
    return bool(markers) and markers <= references


def cited_sources(answer: str, citations: list[dict]) -> list[dict]:
    markers = {int(item) for item in re.findall(r"\[(\d+)\]", answer)}
    return [
        item
        for item in citations
        if int(item["reference"]) in markers
    ]


def score_case(case: dict, retrieval_results: list[dict], answer_payload: dict | None) -> dict:
    rank = first_expected_rank(retrieval_results, case["expected_sources"])
    scored = {
        "id": case["id"],
        "kind": case["kind"],
        "retrieval_hit": rank is not None,
        "reciprocal_rank": 1 / rank if rank else 0.0,
        "retrieval_empty": not retrieval_results,
    }
    if answer_payload is None:
        return scored
    answer = answer_payload.get("answer", "")
    citations = answer_payload.get("citations", [])
    matched, total, coverage = keyword_group_score(answer, case["answer_key_groups"])
    expected = {normalize(item) for item in case["expected_sources"]}
    expected_citations = sum(normalize(item.get("original_filename", "")) in expected for item in citations)
    used_citations = cited_sources(answer, citations)
    expected_used_citations = sum(
        normalize(item.get("original_filename", "")) in expected
        for item in used_citations
    )
    scored.update(
        answer_keyword_groups_matched=matched,
        answer_keyword_groups_total=total,
        answer_keyword_coverage=coverage,
        citation_source_precision=(expected_citations / len(citations) if citations else (1.0 if not expected else 0.0)),
        context_source_precision=(expected_citations / len(citations) if citations else (1.0 if not expected else 0.0)),
        used_citation_source_precision=(
            expected_used_citations / len(used_citations)
            if used_citations else (1.0 if not expected else 0.0)
        ),
        citation_source_hit=bool(expected_citations),
        citation_markers_valid=(citation_marker_valid(answer, citations) if expected else not citations),
        refusal_correct=("无法从当前知识库中确认" in answer if case["kind"] == "unanswerable" else None),
    )
    return scored


def aggregate(scores: list[dict], include_answers: bool) -> dict:
    answerable = [item for item in scores if item["kind"] == "answerable"]
    unanswerable = [item for item in scores if item["kind"] == "unanswerable"]
    mean = lambda values: sum(values) / len(values) if values else 0.0
    summary = {
        "case_count": len(scores),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "retrieval_hit_at_k": mean([item["retrieval_hit"] for item in answerable]),
        "retrieval_mrr": mean([item["reciprocal_rank"] for item in answerable]),
        "unanswerable_retrieval_empty_rate": mean([item["retrieval_empty"] for item in unanswerable]),
    }
    if include_answers:
        summary.update(
            answer_keyword_coverage=mean([item["answer_keyword_coverage"] for item in answerable]),
            citation_source_precision=mean([item["citation_source_precision"] for item in answerable]),
            context_source_precision=mean([
                item.get("context_source_precision", item["citation_source_precision"])
                for item in answerable
            ]),
            used_citation_source_precision=mean([
                item.get("used_citation_source_precision", item["citation_source_precision"])
                for item in answerable
            ]),
            citation_source_hit_rate=mean([item["citation_source_hit"] for item in answerable]),
            citation_marker_valid_rate=mean([item["citation_markers_valid"] for item in answerable]),
            refusal_accuracy=mean([item["refusal_correct"] for item in unanswerable]),
        )
    return summary
