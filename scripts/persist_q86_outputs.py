#!/usr/bin/env python3
"""Persist Q86 outputs atomically with Git Data API, verify bytes, then advance the branch."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "research/q86-six-feature-grammar-20261029"
OUT = "reports/sequence_agent"
OUTPUTS = (
    f"{OUT}/per_number_condition_6plus_grammar.json",
    f"{OUT}/per_number_condition_6plus_checkpoint.json",
    f"{OUT}/per_number_condition_6plus_target_ledger.csv",
) + tuple(f"{OUT}/per_number_condition_6plus_formula_metrics_part_{index:02d}.csv" for index in range(16))
API = "https://api.github.com"


def api(method: str, path: str, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("Q86_PERSIST_BLOCKED: missing GitHub token/repository context")
    url = API + "/repos/" + repo + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "VinciCasa-SONAR-Q86-persistence",
    })
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise SystemExit("Q86_PERSIST_BLOCKED: GitHub API " + str(exc.code) + " " + detail) from exc
    except Exception as exc:
        raise SystemExit("Q86_PERSIST_BLOCKED: GitHub API request failed: " + str(exc)) from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def local_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, text=True
    ).stdout.strip()


def create_blob(path: str) -> str:
    raw = (ROOT / path).read_bytes()
    result = api("POST", "/git/blobs", {
        "content": base64.b64encode(raw).decode("ascii"),
        "encoding": "base64",
    })
    return result["sha"]


def create_tree(base_tree_sha: str, entries: list[dict]) -> str:
    result = api("POST", "/git/trees", {"base_tree": base_tree_sha, "tree": entries})
    return result["sha"]


def create_commit(message: str, tree_sha: str, parent_sha: str) -> str:
    result = api("POST", "/git/commits", {
        "message": message,
        "tree": tree_sha,
        "parents": [parent_sha],
    })
    return result["sha"]


def verify_outputs_at_commit(commit_sha: str, expected_local: dict[str, bytes]):
    commit_info = api("GET", "/git/commits/" + commit_sha)
    tree_info = api("GET", "/git/trees/" + commit_info["tree"]["sha"] + "?recursive=1")
    if tree_info.get("truncated"):
        raise SystemExit("Q86_PERSIST_BLOCKED: repository tree response truncated")
    entries = {
        item["path"]: item
        for item in tree_info.get("tree", [])
        if item.get("type") == "blob"
    }
    for path, expected_bytes in expected_local.items():
        entry = entries.get(path)
        if not entry:
            raise SystemExit("Q86_PERSIST_BLOCKED: persisted tree missing " + path)
        blob = api("GET", "/git/blobs/" + entry["sha"])
        if blob.get("encoding") != "base64":
            raise SystemExit("Q86_PERSIST_BLOCKED: unexpected blob encoding for " + path)
        persisted_bytes = base64.b64decode(blob.get("content", ""))
        if persisted_bytes != expected_bytes:
            raise SystemExit("Q86_PERSIST_BLOCKED: persisted bytes differ for " + path)
        print("Q86_PERSIST_VERIFIED " + path + " bytes=" + str(len(persisted_bytes)))


def main():
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise SystemExit("Q86_PERSIST_BLOCKED: refusing to write outside registered Q86 branch")
    if os.environ.get("GITHUB_EVENT_NAME") != "push":
        raise SystemExit("Q86_PERSIST_BLOCKED: only the registered branch push may persist outputs")
    head = local_head()
    ref = api("GET", "/git/ref/heads/" + BRANCH)
    if ref.get("object", {}).get("sha") != head:
        raise SystemExit("Q86_PERSIST_BLOCKED: branch head changed during evaluation; refusing a race")

    local_bytes = {}
    for path in OUTPUTS:
        file_path = ROOT / path
        if not file_path.is_file():
            raise SystemExit("Q86_PERSIST_BLOCKED: missing validated output " + path)
        local_bytes[path] = file_path.read_bytes()

    head_commit = api("GET", "/git/commits/" + head)
    base_tree = head_commit["tree"]["sha"]
    first_entries = [
        {"path": path, "mode": "100644", "type": "blob", "sha": create_blob(path)}
        for path in OUTPUTS
    ]
    first_tree = create_tree(base_tree, first_entries)
    staged_commit = create_commit(
        "Stage validated Q86 six-feature outputs for byte verification",
        first_tree,
        head,
    )
    verify_outputs_at_commit(staged_commit, local_bytes)

    checkpoint_path = ROOT / f"{OUT}/per_number_condition_6plus_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    validation = checkpoint.setdefault("validation", {})
    validation["persisted_bytes_verified"] = True
    validation["persisted_verified_commit_sha"] = staged_commit
    validation["persisted_verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    validation["exact_head_ci_status"] = "PENDING"
    checkpoint["next_action"] = "Exact-head CI must pass on the persisted branch commit; human review/integration remains required."
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    local_bytes[f"{OUT}/per_number_condition_6plus_checkpoint.json"] = checkpoint_path.read_bytes()

    staged_info = api("GET", "/git/commits/" + staged_commit)
    checkpoint_blob = create_blob(f"{OUT}/per_number_condition_6plus_checkpoint.json")
    final_tree = create_tree(staged_info["tree"]["sha"], [{
        "path": f"{OUT}/per_number_condition_6plus_checkpoint.json",
        "mode": "100644",
        "type": "blob",
        "sha": checkpoint_blob,
    }])
    final_commit = create_commit(
        "Persist Q86 six-feature grammar and verified checkpoint [q86-persisted]",
        final_tree,
        staged_commit,
    )

    # One fast-forward ref update makes the complete output bundle and verification receipt visible together.
    ref_before_update = api("GET", "/git/ref/heads/" + BRANCH)
    if ref_before_update.get("object", {}).get("sha") != head:
        raise SystemExit("Q86_PERSIST_BLOCKED: branch head changed before final ref update")
    api("PATCH", "/git/refs/heads/" + BRANCH, {"sha": final_commit, "force": False})
    verify_outputs_at_commit(final_commit, local_bytes)
    print("Q86_PERSIST_COMMIT " + json.dumps({
        "parent_head": head,
        "staged_commit": staged_commit,
        "persisted_head": final_commit,
        "output_count": len(OUTPUTS),
        "exact_head_ci_status": "PENDING",
        "human_review_required": True,
        "automatic_promotion": False,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
