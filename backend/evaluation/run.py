"""Run the grounded LangChain-course RAG baseline against a live app."""
import argparse
from datetime import UTC, datetime
from getpass import getpass
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

import httpx

from evaluation.metrics import aggregate, score_case


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "langchain_baseline.json"
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_REQUEST_ATTEMPTS = 4


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/api/v1")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--source-dir", type=Path, help="Optional local directory containing the original PDFs")
    parser.add_argument("--mode", choices=("retrieval", "end-to-end"), default="retrieval")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 21), metavar="1..20")
    parser.add_argument("--min-score", type=float, default=0.3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def checked_json(response: httpx.Response) -> dict:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"HTTP {response.status_code}: {detail}") from exc
    return response.json()


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    **kwargs,
) -> dict:
    """Retry transient read/API failures with bounded exponential backoff."""
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        try:
            response = client.request(method, path, **kwargs)
            if (
                response.status_code not in RETRYABLE_STATUS_CODES
                or attempt == MAX_REQUEST_ATTEMPTS
            ):
                return checked_json(response)
        except httpx.TransportError:
            if attempt == MAX_REQUEST_ATTEMPTS:
                raise

        delay = 2 ** (attempt - 1)
        print(
            f"Transient API failure for {path}; "
            f"retrying in {delay}s ({attempt}/{MAX_REQUEST_ATTEMPTS})"
        )
        time.sleep(delay)

    raise RuntimeError("request retry loop ended unexpectedly")


def validate_dataset(dataset: dict) -> None:
    assert dataset.get("version") == 1
    assert dataset.get("name")
    ids = [case["id"] for case in dataset["cases"]]
    assert len(ids) == len(set(ids)) and ids
    source_items = dataset["source_documents"]
    sources = {item["filename"] for item in source_items}
    assert sources and len(sources) == len(source_items)
    for item in dataset["source_documents"]:
        assert len(item["sha256"]) == 64
    for case in dataset["cases"]:
        assert case["kind"] in {"answerable", "unanswerable"}
        assert set(case["expected_sources"]) <= sources
        assert case["answer_key_groups"]
        if case["kind"] == "answerable":
            assert case["expected_sources"]
        else:
            assert not case["expected_sources"]


def verify_source_files(dataset: dict, source_dir: Path) -> None:
    for source in dataset["source_documents"]:
        path = source_dir / source.get("source_path", source["filename"])
        if not path.is_file():
            raise SystemExit(f"Source document missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise SystemExit(f"Source document checksum mismatch: {path}")
    print(f"Source document checksums verified: {len(dataset['source_documents'])}")


def write_checkpoint(
    path: Path,
    dataset: dict,
    args,
    raw_results: list[dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": dataset["name"],
        "dataset_version": dataset["version"],
        "knowledge_base_id": args.knowledge_base_id,
        "mode": args.mode,
        "parameters": {
            "limit": args.limit,
            "min_score": args.min_score,
        },
        "cases": raw_results,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_checkpoint(path: Path, dataset: dict, args) -> list[dict]:
    if not path.is_file():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = (
        dataset["name"],
        dataset["version"],
        args.knowledge_base_id,
        args.mode,
        args.limit,
        args.min_score,
    )
    actual = (
        payload.get("dataset"),
        payload.get("dataset_version"),
        payload.get("knowledge_base_id"),
        payload.get("mode"),
        payload.get("parameters", {}).get("limit"),
        payload.get("parameters", {}).get("min_score"),
    )
    if actual != expected:
        return []

    return list(payload.get("cases", []))


def main() -> None:
    args = parse_args()
    if not -1.0 <= args.min_score <= 1.0:
        raise SystemExit("--min-score must be between -1 and 1")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    if args.source_dir:
        verify_source_files(dataset, args.source_dir)
    output = args.output or Path("../output/evaluation") / f"{dataset['name']}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    checkpoint = output.parent / (
        f".{dataset['name']}-{args.mode}-{args.knowledge_base_id}.partial.json"
    )
    raw_results = load_checkpoint(checkpoint, dataset, args)
    completed = {item["id"] for item in raw_results}
    if completed:
        print(f"Resuming checkpoint: {len(completed)} cases already completed")
    split = urlsplit(args.base_url)
    origin = f"{split.scheme}://{split.netloc}"
    password = getpass(f"Password for {args.username}: ")
    headers = {"Origin": origin, "X-Requested-With": "KnowledgeAssistant"}
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=120) as client:
        identity = request_json(
            client,
            "POST",
            "/auth/login",
            json={"username": args.username, "password": password},
        )
        password = ""
        if identity.get("must_change_password"):
            raise SystemExit("This account must change its password in the browser before evaluation.")
        client.headers.update({"X-CSRF-Token": identity["csrf_token"], "X-Account-ID": identity["id"]})
        docs = request_json(
            client,
            "GET",
            f"/knowledge-bases/{args.knowledge_base_id}/documents",
            params={"limit": 100},
        )
        available = {item["original_filename"]: item["status"] for item in docs["items"]}
        required = {item["filename"] for item in dataset["source_documents"]}
        missing = sorted(required - set(available))
        incomplete = sorted(name for name in required if name in available and available[name] != "completed")
        if missing or incomplete:
            raise SystemExit(f"Corpus preflight failed. Missing={missing}; not completed={incomplete}")

        scores = [item["score"] for item in raw_results]
        for number, case in enumerate(dataset["cases"], start=1):
            if case["id"] in completed:
                print(f"[{number:02}/{len(dataset['cases'])}] {case['id']}: resumed")
                continue
            started = time.perf_counter()
            retrieval = request_json(
                client,
                "POST",
                f"/knowledge-bases/{args.knowledge_base_id}/search",
                json={"query": case["question"], "limit": args.limit, "min_score": args.min_score},
            )
            answer_payload = None
            if args.mode == "end-to-end":
                answer_payload = request_json(
                    client,
                    "POST",
                    f"/knowledge-bases/{args.knowledge_base_id}/answer",
                    json={"question": case["question"], "retrieval_limit": args.limit, "min_score": args.min_score},
                )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            score = score_case(case, retrieval["results"], answer_payload)
            score["latency_ms"] = elapsed_ms
            scores.append(score)
            raw_results.append({
                "id": case["id"], "question": case["question"], "score": score,
                "retrieval": retrieval["results"], "answer": answer_payload,
            })
            write_checkpoint(checkpoint, dataset, args, raw_results)
            print(f"[{number:02}/{len(dataset['cases'])}] {case['id']}: hit={score['retrieval_hit']} {elapsed_ms}ms")

    summary = aggregate(scores, args.mode == "end-to-end")
    summary["mean_case_latency_ms"] = sum(item["latency_ms"] for item in scores) / len(scores)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "dataset": dataset["name"], "dataset_version": dataset["version"],
        "created_at": datetime.now(UTC).isoformat(), "mode": args.mode,
        "parameters": {"limit": args.limit, "min_score": args.min_score},
        "summary": summary, "cases": raw_results,
        "limitations": [
            "Keyword coverage is a deterministic proxy, not semantic answer correctness.",
            "Source-level retrieval labels do not identify every relevant chunk.",
            "No LLM judge or human review score is included.",
        ],
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint.unlink(missing_ok=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {output.resolve()}")


if __name__ == "__main__":
    main()
