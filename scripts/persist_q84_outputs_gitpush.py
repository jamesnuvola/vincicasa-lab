#!/usr/bin/env python3
"""Persist validated Q84 outputs using a bounded local Git push, then verify exact committed bytes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
BRANCH = "research/per-number-condition-grammar-20261026"
OUTPUTS = [
    "strategy_atlas_catalog.jsonl",
    "strategy_atlas_target_ledger.csv",
    "strategy_atlas_lifecycle.json",
    "strategy_atlas_report.json",
    "strategy_atlas_strategy_metrics.csv",
    "strategy_atlas_pair_metrics.csv",
    "strategy_atlas_checkpoint.json",
]


def git(*args: str, capture: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else b""


def fail(message: str) -> None:
    raise SystemExit("Q84_GIT_PERSIST_BLOCKED: " + message)


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_sonar_strategy_atlas import validate_q84

    errors = validate_q84()
    if errors:
        fail("acceptance validator failed: " + "; ".join(errors[:30]))

    subprocess.run([sys.executable, str(ROOT / "scripts" / "sonar_research_queue.py")], cwd=ROOT, check=True)
    queue_path = OUT / "research_queue_status.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    task = next((x for x in queue.get("tasks", []) if x.get("id") == "Q84"), None)
    if queue.get("queue_status") != "QUEUE_VALID" or not task:
        fail("research queue is invalid or Q84 task is missing")
    if task.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"):
        fail("Q84 is not validator-clean and pending human review")

    report_path = OUT / "strategy_atlas_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("task_id") != "Q84" or report.get("review_status") != "PENDING_HUMAN_REVIEW_INTEGRATION":
        fail("Q84 report identity/review guardrail mismatch")

    relpaths = ["reports/sequence_agent/" + name for name in OUTPUTS]
    relpaths.append("reports/sequence_agent/research_queue_status.json")
    manifest_path = OUT / "strategy_atlas_persistence_manifest.json"
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q84",
        "status": "VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION",
        "source_archive_git_blob_sha1": report.get("source_archive_git_blob_sha1"),
        "source_archive_sha256": report.get("source_archive_sha256"),
        "target_count": report.get("target_count"),
        "last_date": report.get("last_date"),
        "scored_targets": report.get("scored_targets"),
        "strategy_count": report.get("strategy_count"),
        "pair_relationship_count": report.get("pair_relationship_count"),
        "files": [],
    }
    payloads = {}
    for rel in relpaths:
        path = ROOT / rel
        if not path.is_file():
            fail("missing output " + rel)
        raw = path.read_bytes()
        payloads[rel] = raw
        manifest["files"].append({
            "path": rel,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_rel = str(manifest_path.relative_to(ROOT))
    payloads[manifest_rel] = manifest_path.read_bytes()
    relpaths.append(manifest_rel)

    local_head = git("rev-parse", "HEAD").decode().strip()
    shallow = git("rev-parse", "--is-shallow-repository").decode().strip() == "true"
    if shallow:
        subprocess.run(["git", "fetch", "--unshallow", "origin", BRANCH], cwd=ROOT, check=True)
    else:
        subprocess.run(["git", "fetch", "origin", BRANCH], cwd=ROOT, check=True)
    remote_head = git("rev-parse", "FETCH_HEAD").decode().strip()
    if local_head != remote_head:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", local_head, remote_head],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if ancestor.returncode != 0:
            fail("remote branch head is not a descendant of this exact checkout; refusing stale persistence")
        subprocess.run(["git", "reset", "--mixed", remote_head], cwd=ROOT, check=True)

    for rel, expected in payloads.items():
        path = ROOT / rel
        if not path.is_file() or path.read_bytes() != expected:
            fail("workspace bytes changed while rebasing onto latest branch: " + rel)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "-f", "--", *relpaths], cwd=ROOT, check=True)

    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    commit_created = staged.returncode != 0
    if commit_created:
        subprocess.run([
            "git", "commit", "-m",
            "Persist validated Q84 event-level strategy atlas and exact-byte manifest [q84-persisted] [q80-validate-persisted]",
        ], cwd=ROOT, check=True)
        commit_sha = git("rev-parse", "HEAD").decode().strip()
        subprocess.run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=ROOT, check=True)
        subprocess.run(["git", "fetch", "origin", BRANCH], cwd=ROOT, check=True)
        observed_remote = git("rev-parse", "FETCH_HEAD").decode().strip()
        if observed_remote != commit_sha:
            fail("remote branch does not point to the new commit after push")
    else:
        commit_sha = remote_head

    verified_bytes = 0
    for rel, expected in payloads.items():
        observed = git("show", commit_sha + ":" + rel)
        if observed != expected:
            fail("exact-byte commit reread mismatch for " + rel)
        verified_bytes += len(observed)
        print("Q84_GIT_PERSIST_VERIFIED: " + rel + " bytes=" + str(len(observed)) +
              " sha256=" + hashlib.sha256(observed).hexdigest())

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("commit_created=" + ("true" if commit_created else "false") + "\n")
            handle.write("commit_sha=" + commit_sha + "\n")
    print(json.dumps({
        "task_id": "Q84",
        "persisted_head_sha": commit_sha,
        "parent_checkout_head": local_head,
        "verified_file_count": len(payloads),
        "verified_bytes": verified_bytes,
        "all_exact_commit_bytes_verified": True,
        "review_status": "PENDING_HUMAN_REVIEW_INTEGRATION",
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
