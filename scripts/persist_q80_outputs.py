#!/usr/bin/env python3
"""Persist validated Q80/Q81/Q82/Q83 formula artifacts with GitHub Git Data API and verify exact-head bytes."""
from __future__ import annotations
import base64
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "research/per-number-condition-grammar-20261026"
Q83_METRICS_REL = "reports/sequence_agent/per_number_condition_5plus_formula_metrics.csv"
Q83_REPORT_REL = "reports/sequence_agent/per_number_condition_5plus_grammar.json"
Q83_MANIFEST_REL = "reports/sequence_agent/per_number_condition_5plus_formula_metrics_manifest.json"
Q83_LEDGER_REL = "reports/sequence_agent/per_number_condition_5plus_target_ledger.csv"
Q83_PART_COUNT = 9
Q83_CHUNK_ROWS = 30000
Q83_PART_PATHS = tuple(
    f"reports/sequence_agent/per_number_condition_5plus_formula_metrics_part_{index:02d}.csv"
    for index in range(Q83_PART_COUNT)
)
DELETE_OUTPUTS = (Q83_METRICS_REL,)
OUTPUTS = (
    "reports/sequence_agent/per_number_condition_grammar.json",
    "reports/sequence_agent/per_number_condition_formula_metrics.csv",
    "reports/sequence_agent/per_number_condition_target_ledger.csv",
    "reports/sequence_agent/per_number_condition_4plus_grammar.json",
    "reports/sequence_agent/per_number_condition_4plus_formula_metrics.csv",
    "reports/sequence_agent/per_number_condition_4plus_target_ledger.csv",
    "reports/sequence_agent/per_number_condition_conditional_grammar.json",
    "reports/sequence_agent/per_number_condition_conditional_metrics.csv",
    "reports/sequence_agent/per_number_condition_conditional_target_ledger.csv",
    Q83_REPORT_REL,
    Q83_MANIFEST_REL,
    *Q83_PART_PATHS,
    Q83_LEDGER_REL,
    "reports/sequence_agent/per_number_condition_research_checkpoint.json",
    "reports/sequence_agent/research_queue_status.json",
    "reports/sequence_agent/latest_metrics.json",
    "reports/sequence_agent/historical_rule_ledger.csv",
    "reports/sequence_agent/draw_signatures.csv",
    "reports/sequence_agent/wave_events.csv",
    "reports/sequence_agent/shadow_forecasts.csv",
    "reports/sequence_agent/archive_reconciliation_2026-10-28.json",
)
API = "https://api.github.com"

def api(method: str, path: str, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: missing GitHub token/repository context")
    url = API + "/repos/" + repo + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "VinciCasa-SONAR-Q80-Q81-Q82-persistence",
    })
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: GitHub API " + str(exc.code) + " " + detail) from exc
    except Exception as exc:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: GitHub API request failed: " + str(exc)) from exc
    return json.loads(raw.decode("utf-8")) if raw else {}

def git_head_file(path: str):
    result = subprocess.run(["git", "show", "HEAD:" + path], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return result.stdout if result.returncode == 0 else None

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_q83_metric_chunks():
    full_path = ROOT / Q83_METRICS_REL
    report_path = ROOT / Q83_REPORT_REL
    manifest_path = ROOT / Q83_MANIFEST_REL
    checkpoint_path = ROOT / "reports/sequence_agent/per_number_condition_research_checkpoint.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    if full_path.is_file():
        with full_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames
            if not fields:
                raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: Q83 metrics CSV has no header")
            part_rows = []
            part_index = -1
            part_handle = None
            writer = None
            total_rows = 0
            try:
                for row in reader:
                    if total_rows % Q83_CHUNK_ROWS == 0:
                        if part_handle:
                            part_handle.close()
                        part_index += 1
                        if part_index >= Q83_PART_COUNT:
                            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: Q83 metrics exceed registered chunk capacity")
                        part_path = ROOT / Q83_PART_PATHS[part_index]
                        part_path.parent.mkdir(parents=True, exist_ok=True)
                        part_handle = part_path.open("w", newline="", encoding="utf-8")
                        writer = csv.DictWriter(part_handle, fieldnames=fields)
                        writer.writeheader()
                        part_rows.append(0)
                    writer.writerow(row)
                    part_rows[part_index] += 1
                    total_rows += 1
            finally:
                if part_handle:
                    part_handle.close()
        expected_rows = int(report.get("metrics_rows", -1))
        if total_rows != expected_rows:
            raise SystemExit(f"Q80_Q81_Q82_Q83_PERSIST_BLOCKED: Q83 chunk row count {total_rows} != report {expected_rows}")
        if part_index + 1 != Q83_PART_COUNT:
            raise SystemExit(f"Q80_Q81_Q82_Q83_PERSIST_BLOCKED: Q83 chunk count {part_index + 1} != {Q83_PART_COUNT}")
        manifest = []
        cursor = 0
        for index, rows in enumerate(part_rows):
            path = ROOT / Q83_PART_PATHS[index]
            manifest.append({
                "part_index": index,
                "path": Q83_PART_PATHS[index],
                "rows": rows,
                "row_start_inclusive": cursor,
                "row_end_exclusive": cursor + rows,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
            cursor += rows
        full_path.unlink()
    else:
        manifest = report.get("metrics_parts", [])
        if len(manifest) != Q83_PART_COUNT or report.get("metrics_storage") != "chunked_csv_parts":
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: neither source Q83 CSV nor valid chunk manifest exists")
        cursor = 0
        for index, item in enumerate(manifest):
            path = ROOT / item.get("path", "")
            if item.get("part_index") != index or int(item.get("row_start_inclusive", -1)) != cursor or not path.is_file():
                raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: existing Q83 chunk manifest is incomplete")
            if path.stat().st_size != int(item.get("bytes", -1)) or sha256_file(path) != item.get("sha256"):
                raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: existing Q83 chunk checksum mismatch")
            cursor += int(item.get("rows", 0))
        if cursor != int(report.get("metrics_rows", -1)):
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: existing Q83 chunk row coverage mismatch")

    manifest_list_sha = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    report["metrics_storage"] = "chunked_csv_parts"
    report["metrics_parts"] = manifest
    report.setdefault("outputs", {})["metrics"] = None
    report["outputs"]["metrics_parts"] = [item["path"] for item in manifest]
    report["outputs"]["metrics_manifest"] = Q83_MANIFEST_REL
    report["outputs"]["metrics_parts_manifest_sha256"] = manifest_list_sha
    manifest_document = {
        "schema_version": "1.0",
        "task_id": "Q83",
        "storage_format": "chunked_csv_parts",
        "source_archive_sha256": report.get("source_archive_sha256"),
        "formula_count": report.get("formula_count"),
        "metrics_rows": report.get("metrics_rows"),
        "part_count": len(manifest),
        "parts_manifest_sha256": manifest_list_sha,
        "parts": manifest,
    }
    manifest_path.write_text(json.dumps(manifest_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_file_sha = sha256_file(manifest_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        manifest_blob_sha = subprocess.run(
            ["git", "hash-object", str(manifest_path)], cwd=ROOT, check=True,
            stdout=subprocess.PIPE, text=True
        ).stdout.strip()
        report_blob_sha = subprocess.run(
            ["git", "hash-object", str(report_path)], cwd=ROOT, check=True,
            stdout=subprocess.PIPE, text=True
        ).stdout.strip()
        for milestone in checkpoint.get("verified_milestones", []):
            if milestone.get("id") == "Q83":
                outputs = milestone.setdefault("outputs", {})
                outputs.pop("metrics_blob_sha", None)
                outputs["metrics_parts"] = manifest
                outputs["metrics_manifest_sha256"] = manifest_list_sha
                outputs["metrics_manifest_path"] = Q83_MANIFEST_REL
                outputs["metrics_manifest_blob_sha"] = manifest_blob_sha
                outputs["metrics_manifest_file_sha256"] = manifest_file_sha
                outputs["report_blob_sha"] = report_blob_sha
                milestone["metrics_storage"] = "chunked_csv_parts"
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def verify_outputs_at_ref(ref_sha: str):
    # Re-read immutable Git objects by exact commit SHA, not mutable branch paths.
    commit_info = api("GET", "/git/commits/" + ref_sha)
    tree_info = api("GET", "/git/trees/" + commit_info["tree"]["sha"] + "?recursive=1")
    if tree_info.get("truncated"):
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: repository tree response was truncated")
    entries = {item["path"]: item for item in tree_info.get("tree", []) if item.get("type") == "blob"}
    for path in OUTPUTS:
        entry = entries.get(path)
        if not entry:
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: persisted tree missing " + path)
        blob = api("GET", "/git/blobs/" + entry["sha"])
        if blob.get("encoding") != "base64":
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: unexpected blob encoding for " + path)
        persisted_bytes = base64.b64decode(blob.get("content", ""))
        expected_bytes = (ROOT / path).read_bytes()
        if persisted_bytes != expected_bytes:
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: persisted bytes differ for " + path)
        print("Q80_Q81_Q82_Q83_PERSIST_VERIFIED: " + path + " bytes=" + str(len(persisted_bytes)))
    for path in DELETE_OUTPUTS:
        if path in entries:
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: oversized monolithic metrics CSV still present: " + path)

def main():
    effective_ref = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if effective_ref != BRANCH:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: refusing to write outside the registered research branch")
    head_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True)
    head = head_result.stdout.strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not head or not repo:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: missing checkout/repository context")
    prepare_q83_metric_chunks()
    sys.path.insert(0, str(ROOT / "scripts"))
    from sonar_research_queue import validate_q80, validate_q81, validate_q82, validate_q83
    errors = validate_q80() + validate_q81() + validate_q82() + validate_q83()
    if errors:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: acceptance validation failed: " + "; ".join(errors))
    report80 = json.loads((ROOT / "reports/sequence_agent/per_number_condition_grammar.json").read_text(encoding="utf-8"))
    report81 = json.loads((ROOT / "reports/sequence_agent/per_number_condition_4plus_grammar.json").read_text(encoding="utf-8"))
    report82 = json.loads((ROOT / "reports/sequence_agent/per_number_condition_conditional_grammar.json").read_text(encoding="utf-8"))
    report83 = json.loads((ROOT / Q83_REPORT_REL).read_text(encoding="utf-8"))
    queue = json.loads((ROOT / "reports/sequence_agent/research_queue_status.json").read_text(encoding="utf-8"))
    q80 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q80"), None)
    q81 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q81"), None)
    q82 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q82"), None)
    q83 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q83"), None)
    for task_id, report in (("Q80", report80), ("Q81", report81), ("Q82", report82), ("Q83", report83)):
        if report.get("review_status") != "PENDING_HUMAN_REVIEW_INTEGRATION":
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: " + task_id + " report does not preserve human-review gate")
    if (queue.get("queue_status") != "QUEUE_VALID" or
        not q80 or q80.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q80.get("validation_errors") or
        not q81 or q81.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q81.get("validation_errors") or
        not q82 or q82.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q82.get("validation_errors") or
        not q83 or q83.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q83.get("validation_errors")):
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: queue status is not validated/pending review")
    changed = []
    for path in OUTPUTS:
        content = (ROOT / path).read_bytes()
        previous = git_head_file(path)
        if previous != content:
            changed.append((path, content.decode("utf-8")))
    deleted = [path for path in DELETE_OUTPUTS if git_head_file(path) is not None]
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not changed and not deleted:
        ref_now = api("GET", "/git/ref/heads/" + BRANCH)
        if ref_now.get("object", {}).get("sha") != head:
            raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: branch head moved before no-op verification")
        verify_outputs_at_ref(head)
        if output_path:
            with open(output_path, "a", encoding="utf-8") as handle:
                handle.write("commit_created=false\nnew_sha=" + head + "\n")
        print("Q80_Q81_Q82_Q83_PERSIST_NOOP: validated outputs already match the branch head")
        return
    ref = api("GET", "/git/ref/heads/" + BRANCH)
    if ref.get("object", {}).get("sha") != head:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: branch head moved during validation; refusing stale write")
    commit_data = api("GET", "/git/commits/" + head)
    tree_entries = []
    for path, content in changed:
        blob = api("POST", "/git/blobs", {"content": content, "encoding": "utf-8"})
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("Q80_Q81_Q82_Q83_PERSIST_BLOB: " + path + " bytes=" + str(len(content.encode("utf-8"))))
    tree_entries.extend({"path": path, "mode": "100644", "type": "blob", "sha": None} for path in deleted)
    tree = api("POST", "/git/trees", {"base_tree": commit_data["tree"]["sha"], "tree": tree_entries})
    commit = api("POST", "/git/commits", {
        "message": "Persist validated Q80-Q83 formula outputs, archive sync, checkpoint and research queue status",
        "tree": tree["sha"],
        "parents": [head],
    })
    api("PATCH", "/git/refs/heads/" + BRANCH, {"sha": commit["sha"], "force": False})
    ref_after = api("GET", "/git/ref/heads/" + BRANCH)
    if ref_after.get("object", {}).get("sha") != commit["sha"]:
        raise SystemExit("Q80_Q81_Q82_Q83_PERSIST_BLOCKED: branch ref does not point to persisted commit")
    verify_outputs_at_ref(commit["sha"])
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("commit_created=true\nnew_sha=" + commit["sha"] + "\n")
    print("Q80_Q81_Q82_Q83_PERSIST_COMMIT: " + commit["sha"])

if __name__ == "__main__":
    main()
