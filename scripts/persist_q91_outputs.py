#!/usr/bin/env python3
"""Persist Q91 validated outputs via Git Data API and verify exact immutable Git object bytes."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from validate_sonar_q91_nested_walkforward import validate_outputs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
BRANCH = "research/q91-nested-formula-walkforward-20261105"
API = "https://api.github.com"
REPORT_REL = "reports/sequence_agent/q91_nested_formula_walkforward.json"
SCORE_MANIFEST_REL = "reports/sequence_agent/q91_formula_target_scores_manifest.json"
CHECKPOINT_PREFIX = "reports/sequence_agent/q91_checkpoint_"
QUEUE_REL = "reports/sequence_agent/research_queue_status.json"


def api(method: str, path: str, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("Q91_PERSIST_BLOCKED: missing GitHub token/repository context")
    url = API + "/repos/" + repo + path
    data = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "VinciCasa-SONAR-Q91-persistence",
    })
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise SystemExit("Q91_PERSIST_BLOCKED: GitHub API " + str(exc.code) + " " + detail) from exc
    except Exception as exc:
        raise SystemExit("Q91_PERSIST_BLOCKED: GitHub API request failed: " + str(exc)) from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_head_file(path: str):
    result = subprocess.run(
        ["git", "show", "HEAD:" + path], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    return result.stdout if result.returncode == 0 else None


def collect_output_paths():
    report = json.loads((ROOT / REPORT_REL).read_text(encoding="utf-8"))
    score_manifest = json.loads((ROOT / SCORE_MANIFEST_REL).read_text(encoding="utf-8"))
    checkpoint_rel = report.get("outputs", {}).get("checkpoint")
    if not checkpoint_rel or not (ROOT / checkpoint_rel).is_file():
        raise SystemExit("Q91_PERSIST_BLOCKED: checkpoint path missing")
    part_paths = [item.get("path", "") for item in score_manifest.get("parts", [])]
    if not part_paths or any(not p or not (ROOT / p).is_file() for p in part_paths):
        raise SystemExit("Q91_PERSIST_BLOCKED: score parts are incomplete")
    paths = [
        "reports/sequence_agent/q91_formula_catalog.csv",
        "reports/sequence_agent/q91_policy_metrics.csv",
        "reports/sequence_agent/q91_target_ledger.csv",
        "reports/sequence_agent/q91_formula_selection_report.json",
        SCORE_MANIFEST_REL,
        *part_paths,
        REPORT_REL,
        checkpoint_rel,
        QUEUE_REL,
    ]
    if len(paths) != len(set(paths)):
        raise SystemExit("Q91_PERSIST_BLOCKED: duplicate output path")
    for path in paths:
        if not (ROOT / path).is_file():
            raise SystemExit("Q91_PERSIST_BLOCKED: output file missing " + path)
    return paths, checkpoint_rel


def tree_entries_at_ref(ref_sha: str):
    commit_info = api("GET", "/git/commits/" + ref_sha)
    tree_info = api("GET", "/git/trees/" + commit_info["tree"]["sha"] + "?recursive=1")
    if tree_info.get("truncated"):
        raise SystemExit("Q91_PERSIST_BLOCKED: repository tree response was truncated")
    return {item["path"]: item for item in tree_info.get("tree", []) if item.get("type") == "blob"}


def stale_output_paths(ref_sha: str, expected_paths):
    entries = tree_entries_at_ref(ref_sha)
    keep = set(expected_paths)
    stale = []
    for path in entries:
        is_score_part = path.startswith("reports/sequence_agent/q91_formula_target_scores_part_") and path.endswith(".npz")
        is_checkpoint = path.startswith("reports/sequence_agent/q91_checkpoint_") and path.endswith(".json")
        if (is_score_part or is_checkpoint) and path not in keep:
            stale.append(path)
    return sorted(stale)


def verify_outputs_at_ref(ref_sha: str, paths, deleted_paths=()):
    entries = tree_entries_at_ref(ref_sha)
    for path in paths:
        entry = entries.get(path)
        if not entry:
            raise SystemExit("Q91_PERSIST_BLOCKED: persisted tree missing " + path)
        blob = api("GET", "/git/blobs/" + entry["sha"])
        if blob.get("encoding") != "base64":
            raise SystemExit("Q91_PERSIST_BLOCKED: unexpected blob encoding for " + path)
        persisted_bytes = base64.b64decode(blob.get("content", ""))
        expected_bytes = (ROOT / path).read_bytes()
        if persisted_bytes != expected_bytes:
            raise SystemExit("Q91_PERSIST_BLOCKED: persisted bytes differ for " + path)
        if sha256_bytes(persisted_bytes) != sha256_bytes(expected_bytes):
            raise SystemExit("Q91_PERSIST_BLOCKED: SHA readback mismatch for " + path)
        print("Q91_PERSIST_VERIFIED:", path, "bytes=" + str(len(persisted_bytes)),
              "sha256=" + sha256_bytes(persisted_bytes))
    for path in deleted_paths:
        if path in entries:
            raise SystemExit("Q91_PERSIST_BLOCKED: stale output remains in persisted tree " + path)
        print("Q91_PERSIST_DELETED_VERIFIED:", path)


def main():
    effective_ref = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if effective_ref and effective_ref != BRANCH:
        raise SystemExit("Q91_PERSIST_BLOCKED: refusing to write outside registered research branch")
    expected_head = os.environ.get("GITHUB_HEAD_SHA")
    if not expected_head:
        raise SystemExit("Q91_PERSIST_BLOCKED: missing expected research branch head SHA")

    errors = validate_outputs()
    if errors:
        raise SystemExit("Q91_PERSIST_BLOCKED: acceptance validator errors: " + " | ".join(errors[:20]))

    report_path = ROOT / REPORT_REL
    report = json.loads(report_path.read_text(encoding="utf-8"))
    acceptance = report.get("acceptance", {})
    acceptance.update({
        "validator": "Q91_FORMULA_ACCEPTANCE_PASS",
        "artifact_readback": "PENDING_EXACT_GIT_OBJECT_READBACK",
        "current_head_ci": "PENDING",
        "human_review": "PENDING_HUMAN_REVIEW_INTEGRATION",
        "persisted_parent_head_sha": expected_head,
        "persist_workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
    })
    report["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
    report["acceptance"] = acceptance
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _, checkpoint_rel = collect_output_paths()
    checkpoint_path = ROOT / checkpoint_rel
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["status"] = "VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION"
    checkpoint["acceptance"] = acceptance
    checkpoint["report_sha256"] = sha256_bytes(report_path.read_bytes())
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    errors = validate_outputs()
    if errors:
        raise SystemExit("Q91_PERSIST_BLOCKED: post-status validator errors: " + " | ".join(errors[:20]))

    subprocess.run(
        ["python", str(ROOT / "scripts" / "sonar_research_queue.py")],
        cwd=ROOT, check=True
    )
    queue = json.loads((ROOT / QUEUE_REL).read_text(encoding="utf-8"))
    q91 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q91"), None)
    if not q91 or q91.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q91.get("validation_errors"):
        raise SystemExit("Q91_PERSIST_BLOCKED: refreshed queue is not validator-clean/pending human review")

    paths, checkpoint_rel = collect_output_paths()
    ref = api("GET", "/git/ref/heads/" + BRANCH)
    head = ref.get("object", {}).get("sha")
    if head != expected_head:
        raise SystemExit("Q91_PERSIST_BLOCKED: branch head moved during validation; refusing stale write")

    changed = []
    for path in paths:
        content = (ROOT / path).read_bytes()
        previous = git_head_file(path)
        if previous != content:
            changed.append((path, content))
    deleted_paths = stale_output_paths(head, paths)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not changed and not deleted_paths:
        verify_outputs_at_ref(head, paths)
        if output_path:
            with open(output_path, "a", encoding="utf-8") as handle:
                handle.write("commit_created=false\nnew_sha=" + head + "\n")
        print("Q91_PERSIST_NOOP: validated outputs already match branch head")
        return

    commit_data = api("GET", "/git/commits/" + head)
    tree_entries = []
    for path, content in changed:
        blob = api("POST", "/git/blobs", {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        })
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("Q91_PERSIST_BLOB:", path, "bytes=" + str(len(content)), "sha=" + blob["sha"])
    tree_entries.extend({"path": path, "mode": "100644", "type": "blob", "sha": None} for path in deleted_paths)
    tree = api("POST", "/git/trees", {
        "base_tree": commit_data["tree"]["sha"],
        "tree": tree_entries,
    })
    commit = api("POST", "/git/commits", {
        "message": "Persist validated Q91 nested formula walk-forward outputs, score chunks and queue checkpoint [q91-persisted]",
        "tree": tree["sha"],
        "parents": [head],
    })
    api("PATCH", "/git/refs/heads/" + BRANCH, {"sha": commit["sha"], "force": False})
    ref_after = api("GET", "/git/ref/heads/" + BRANCH)
    if ref_after.get("object", {}).get("sha") != commit["sha"]:
        raise SystemExit("Q91_PERSIST_BLOCKED: branch ref does not point to persisted commit")
    verify_outputs_at_ref(commit["sha"], paths, deleted_paths)
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("commit_created=true\nnew_sha=" + commit["sha"] + "\n")
    print("Q91_PERSIST_COMMIT:", commit["sha"])


if __name__ == "__main__":
    main()
