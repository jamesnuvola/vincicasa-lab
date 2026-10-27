#!/usr/bin/env python3
"""Validate and persist Q81 outputs through Git Data API without Contents API races."""
from __future__ import annotations
import csv
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "research/per-number-condition-grammar-q81-20261027"
OUT = ROOT / "reports" / "sequence_agent"
REPORT = OUT / "per_number_condition_four_feature_grammar.json"
METRICS = OUT / "per_number_condition_four_feature_metrics.csv"
LEDGER = OUT / "per_number_condition_four_feature_target_ledger.csv"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
OUTPUTS = (str(REPORT.relative_to(ROOT)), str(METRICS.relative_to(ROOT)), str(LEDGER.relative_to(ROOT)))
API = "https://api.github.com"


def api(method: str, path: str, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("Q81_PERSIST_BLOCKED: missing GitHub token/repository context")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(API + "/repos/" + repo + path, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "VinciCasa-SONAR-Q81-persistence",
    })
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise SystemExit("Q81_PERSIST_BLOCKED: GitHub API " + str(exc.code) + " " + detail) from exc
    except Exception as exc:
        raise SystemExit("Q81_PERSIST_BLOCKED: GitHub API request failed: " + str(exc)) from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def git_head_file(path: str):
    result = subprocess.run(["git", "show", "HEAD:" + path], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return result.stdout if result.returncode == 0 else None


def validate_bundle():
    if not REPORT.is_file() or not METRICS.is_file() or not LEDGER.is_file() or not ARCHIVE.is_file():
        raise SystemExit("Q81_PERSIST_BLOCKED: required Q81 output/archive missing")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    with ARCHIVE.open(newline="", encoding="utf-8-sig") as handle:
        archive_rows = list(csv.DictReader(handle))
    dates, draws = [], []
    for row in archive_rows:
        nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
        if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n < 1 or n > 40 for n in nums):
            raise SystemExit("Q81_PERSIST_BLOCKED: invalid canonical draw at " + row["data"])
        dates.append(row["data"]); draws.append(nums)
    if any(dates[i] <= dates[i-1] for i in range(1, len(dates))):
        raise SystemExit("Q81_PERSIST_BLOCKED: archive dates are not strictly chronological")
    expected = math.comb(27, 4)
    if report.get("task_id") != "Q81" or report.get("status") != "VALIDATED_FINITE_GRAMMAR_COMPLETE":
        raise SystemExit("Q81_PERSIST_BLOCKED: report status/task mismatch")
    if report.get("review_status") != "PENDING_HUMAN_REVIEW_INTEGRATION":
        raise SystemExit("Q81_PERSIST_BLOCKED: human review gate not preserved")
    if report.get("formula_count") != expected or report.get("formula_count_check") != expected:
        raise SystemExit("Q81_PERSIST_BLOCKED: formula count mismatch")
    if report.get("target_count") != len(draws) or report.get("first_date") != dates[0] or report.get("last_date") != dates[-1]:
        raise SystemExit("Q81_PERSIST_BLOCKED: archive reconciliation mismatch")
    with METRICS.open(newline="", encoding="utf-8") as handle:
        metric_rows = list(csv.DictReader(handle))
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        ledger_rows = list(csv.DictReader(handle))
    split_counts = report.get("split_counts", {})
    if len(metric_rows) != expected * 3 or len(metric_rows) != report.get("metrics_rows"):
        raise SystemExit("Q81_PERSIST_BLOCKED: metrics row count mismatch")
    if len(ledger_rows) != len(draws) - 50 or len(ledger_rows) != report.get("target_ledger_rows"):
        raise SystemExit("Q81_PERSIST_BLOCKED: ledger row count mismatch")
    expected_splits = {"discovery": 2003, "validation": 668, "blind_oos": 667}
    if split_counts != expected_splits:
        raise SystemExit("Q81_PERSIST_BLOCKED: chronological split count mismatch")
    ids = {name: set() for name in expected_splits}
    counts = {name: 0 for name in expected_splits}
    for row in metric_rows:
        split = row["split"]
        if split not in ids or int(row["feature_count"]) != 4 or int(row["targets"]) != expected_splits[split]:
            raise SystemExit("Q81_PERSIST_BLOCKED: invalid metric split/feature/target count")
        ids[split].add(row["formula_id"]); counts[split] += 1
        if not 0 <= float(row["holm_p_max_endpoint_family"]) <= 1:
            raise SystemExit("Q81_PERSIST_BLOCKED: invalid adjusted p-value")
    for split in expected_splits:
        if counts[split] != expected or len(ids[split]) != expected:
            raise SystemExit("Q81_PERSIST_BLOCKED: formula coverage mismatch in " + split)
    for k, row in enumerate(ledger_rows):
        i = k + 50
        if (row["target_date"] != dates[i] or row["cutoff_date"] != dates[i-1]
                or int(row["prior_draws"]) != i
                or row["actual_quintet"] != " ".join(map(str, draws[i]))
                or row["status"] != "SCORED" or int(row["formula_count_tested"]) != expected):
            raise SystemExit("Q81_PERSIST_BLOCKED: target/cutoff/archive mismatch at " + dates[i])
        ranks = json.loads(row["best_actual_number_ranks"])
        if (len(ranks) != 5 or any(x < 1 or x > 40 for x in ranks)
                or sum(ranks) != int(row["best_rank_sum"])
                or sum(x <= 5 for x in ranks) != int(row["best_number_hits_top5"])
                or sum(x <= 10 for x in ranks) != int(row["best_number_hits_top10"])
                or sum(x <= 20 for x in ranks) != int(row["best_number_hits_top20"])):
            raise SystemExit("Q81_PERSIST_BLOCKED: rank ledger inconsistency at " + dates[i])
    print("Q81_ACCEPTANCE_PASS: archive=" + str(len(draws)) + " formulas=" + str(expected)
          + " metrics=" + str(len(metric_rows)) + " targets=" + str(len(ledger_rows)))


def main():
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise SystemExit("Q81_PERSIST_BLOCKED: refusing to write outside the registered research branch")
    head = os.environ.get("GITHUB_SHA", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not head or not repo:
        raise SystemExit("Q81_PERSIST_BLOCKED: missing commit/repository context")
    validate_bundle()
    changed = []
    for path in OUTPUTS:
        content = (ROOT / path).read_bytes()
        if git_head_file(path) != content:
            changed.append((path, content.decode("utf-8")))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not changed:
        if output_path:
            with open(output_path, "a", encoding="utf-8") as handle:
                handle.write("commit_created=false\nnew_sha=" + head + "\n")
        print("Q81_PERSIST_NOOP: validated outputs already match branch head")
        return
    ref = api("GET", "/git/ref/heads/" + BRANCH)
    if ref.get("object", {}).get("sha") != head:
        raise SystemExit("Q81_PERSIST_BLOCKED: branch head moved during validation; refusing stale write")
    commit_data = api("GET", "/git/commits/" + head)
    entries = []
    for path, content in changed:
        blob = api("POST", "/git/blobs", {"content": content, "encoding": "utf-8"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("Q81_PERSIST_BLOB: " + path + " bytes=" + str(len(content.encode("utf-8"))))
    tree = api("POST", "/git/trees", {"base_tree": commit_data["tree"]["sha"], "tree": entries})
    commit = api("POST", "/git/commits", {
        "message": "Persist validated Q81 four-feature grammar outputs",
        "tree": tree["sha"], "parents": [head],
    })
    api("PATCH", "/git/refs/heads/" + BRANCH, {"sha": commit["sha"], "force": False})
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("commit_created=true\nnew_sha=" + commit["sha"] + "\n")
    print("Q81_PERSIST_COMMIT: " + commit["sha"])


if __name__ == "__main__":
    main()
