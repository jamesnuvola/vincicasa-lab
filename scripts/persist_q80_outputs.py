#!/usr/bin/env python3
"""Persist validated Q80/Q81/Q82 formula artifacts with GitHub's Git Data API, then request exact-head CI."""
from __future__ import annotations
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "research/per-number-condition-grammar-20261026"
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
    "reports/sequence_agent/per_number_condition_research_checkpoint.json",
    "reports/sequence_agent/research_queue_status.json",
)
API = "https://api.github.com"

def api(method: str, path: str, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: missing GitHub token/repository context")
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
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: GitHub API " + str(exc.code) + " " + detail) from exc
    except Exception as exc:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: GitHub API request failed: " + str(exc)) from exc
    return json.loads(raw.decode("utf-8")) if raw else {}

def git_head_file(path: str):
    result = subprocess.run(["git", "show", "HEAD:" + path], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return result.stdout if result.returncode == 0 else None



def verify_outputs_at_ref(ref_sha: str):
    # Re-read immutable Git objects by exact commit SHA, not mutable branch paths.
    commit_info = api("GET", "/git/commits/" + ref_sha)
    tree_info = api("GET", "/git/trees/" + commit_info["tree"]["sha"] + "?recursive=1")
    if tree_info.get("truncated"):
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: repository tree response was truncated")
    entries = {item["path"]: item for item in tree_info.get("tree", []) if item.get("type") == "blob"}
    for path in OUTPUTS:
        entry = entries.get(path)
        if not entry:
            raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: persisted tree missing " + path)
        blob = api("GET", "/git/blobs/" + entry["sha"])
        if blob.get("encoding") != "base64":
            raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: unexpected blob encoding for " + path)
        persisted_bytes = base64.b64decode(blob.get("content", ""))
        expected_bytes = (ROOT / path).read_bytes()
        if persisted_bytes != expected_bytes:
            raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: persisted bytes differ for " + path)
        print("Q80_Q81_Q82_PERSIST_VERIFIED: " + path + " bytes=" + str(len(persisted_bytes)))

def main():
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: refusing to write outside the registered research branch")
    head = os.environ.get("GITHUB_SHA", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not head or not repo:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: missing commit/repository context")
    sys.path.insert(0, str(ROOT / "scripts"))
    from sonar_research_queue import validate_q80, validate_q81, validate_q82
    errors = validate_q80() + validate_q81() + validate_q82()
    if errors:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: acceptance validation failed: " + "; ".join(errors))
    report80 = json.loads((ROOT / OUTPUTS[0]).read_text(encoding="utf-8"))
    report81 = json.loads((ROOT / OUTPUTS[3]).read_text(encoding="utf-8"))
    report82 = json.loads((ROOT / OUTPUTS[6]).read_text(encoding="utf-8"))
    queue = json.loads((ROOT / OUTPUTS[10]).read_text(encoding="utf-8"))
    q80 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q80"), None)
    q81 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q81"), None)
    q82 = next((item for item in queue.get("tasks", []) if item.get("id") == "Q82"), None)
    for task_id, report in (("Q80", report80), ("Q81", report81), ("Q82", report82)):
        if report.get("review_status") != "PENDING_HUMAN_REVIEW_INTEGRATION":
            raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: " + task_id + " report does not preserve human-review gate")
    if (queue.get("queue_status") != "QUEUE_VALID" or
        not q80 or q80.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q80.get("validation_errors") or
        not q81 or q81.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q81.get("validation_errors") or
        not q82 or q82.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or q82.get("validation_errors")):
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: queue status is not validated/pending review")
    changed = []
    for path in OUTPUTS:
        content = (ROOT / path).read_bytes()
        previous = git_head_file(path)
        if previous != content:
            changed.append((path, content.decode("utf-8")))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not changed:
        ref_now = api("GET", "/git/ref/heads/" + BRANCH)
        if ref_now.get("object", {}).get("sha") != head:
            raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: branch head moved before no-op verification")
        verify_outputs_at_ref(head)
        if output_path:
            with open(output_path, "a", encoding="utf-8") as handle:
                handle.write("commit_created=false\nnew_sha=" + head + "\n")
        print("Q80_Q81_Q82_PERSIST_NOOP: validated outputs already match the branch head")
        return
    ref = api("GET", "/git/ref/heads/" + BRANCH)
    if ref.get("object", {}).get("sha") != head:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: branch head moved during validation; refusing stale write")
    commit_data = api("GET", "/git/commits/" + head)
    tree_entries = []
    for path, content in changed:
        blob = api("POST", "/git/blobs", {"content": content, "encoding": "utf-8"})
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("Q80_Q81_Q82_PERSIST_BLOB: " + path + " bytes=" + str(len(content.encode("utf-8"))))
    tree = api("POST", "/git/trees", {"base_tree": commit_data["tree"]["sha"], "tree": tree_entries})
    commit = api("POST", "/git/commits", {
        "message": "Persist validated Q80/Q81/Q82 formula outputs, checkpoint and research queue status",
        "tree": tree["sha"],
        "parents": [head],
    })
    api("PATCH", "/git/refs/heads/" + BRANCH, {"sha": commit["sha"], "force": False})
    ref_after = api("GET", "/git/ref/heads/" + BRANCH)
    if ref_after.get("object", {}).get("sha") != commit["sha"]:
        raise SystemExit("Q80_Q81_Q82_PERSIST_BLOCKED: branch ref does not point to persisted commit")
    verify_outputs_at_ref(commit["sha"])
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("commit_created=true\nnew_sha=" + commit["sha"] + "\n")
    print("Q80_Q81_Q82_PERSIST_COMMIT: " + commit["sha"])

if __name__ == "__main__":
    main()
