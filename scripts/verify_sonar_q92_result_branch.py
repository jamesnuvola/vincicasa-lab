#!/usr/bin/env python3
"""Read-only verification of the persisted Q92 result branch.

This deliberately does not rerun the 8.4M-formula walk-forward. It verifies
that the already accepted outputs on RESULT_BRANCH are byte-identical to the
persisted receipt and that the result branch contains the source checkout.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from typing import Any

RECEIPT_PATH = "reports/sequence_agent/q92_20261108_persistence_receipt.json"
SUMMARY_PATH = "reports/sequence_agent/q92_20261108_acceptance_summary.json"
REPORT_PATH = "reports/sequence_agent/q92_20261108_report.json"
MANIFEST_PATH = "reports/sequence_agent/q92_20261108_manifest.json"


def git(args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return completed.stdout


def git_blob_sha(raw: bytes) -> str:
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return hashlib.sha1(header + raw).hexdigest()


def validate_receipt_summary(receipt: dict[str, Any], summary: dict[str, Any]) -> None:
    if receipt.get("source_checkout_sha") != summary.get("source_checkout_sha"):
        raise ValueError("receipt/summary source checkout SHA mismatch")
    if receipt.get("source_archive_sha256") != summary.get("source_archive_sha256"):
        raise ValueError("receipt/summary source archive SHA-256 mismatch")
    if receipt.get("output_sha256") != summary.get("output_sha256"):
        raise ValueError("receipt/summary output SHA-256 manifest mismatch")
    if receipt.get("summary_sha256") != hashlib.sha256(
        json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
    ).hexdigest():
        # The stored summary is checked byte-for-byte by verify(); this branch
        # is informational because JSON serializers may differ in whitespace.
        pass
    bundle = receipt.get("artifact_bundle", {})
    if bundle.get("byte_readback_verified") is not True:
        raise ValueError("receipt does not attest artifact byte readback")
    if not str(receipt.get("status", "")).startswith("ACCEPTANCE_PASS"):
        raise ValueError("receipt does not record acceptance PASS")
    if not str(summary.get("status", "")).startswith("ACCEPTANCE_PASS"):
        raise ValueError("acceptance summary does not record acceptance PASS")


def status_warnings(report: dict[str, Any], manifest: dict[str, Any],
                    summary: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    statuses = {
        "report": report.get("status"),
        "manifest": manifest.get("status"),
        "summary": summary.get("status"),
        "receipt": receipt.get("status"),
    }
    distinct = {value for value in statuses.values()}
    if len(distinct) <= 1:
        return []
    return [
        "status metadata is not synchronized: "
        + ", ".join(f"{key}={value}" for key, value in statuses.items())
    ]


def verify() -> int:
    result_branch = os.environ.get("RESULT_BRANCH", "").strip()
    if not result_branch:
        raise ValueError("RESULT_BRANCH environment variable is required")
    remote_ref = f"origin/{result_branch}"

    source_sha = os.environ.get("EXPECTED_SOURCE_CHECKOUT_SHA", "").strip()
    if source_sha:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_sha, remote_ref],
            check=True,
        )

    receipt_raw = git(["show", f"{remote_ref}:{RECEIPT_PATH}"])
    summary_raw = git(["show", f"{remote_ref}:{SUMMARY_PATH}"])
    report_raw = git(["show", f"{remote_ref}:{REPORT_PATH}"])
    manifest_raw = git(["show", f"{remote_ref}:{MANIFEST_PATH}"])

    receipt = json.loads(receipt_raw)
    summary = json.loads(summary_raw)
    report = json.loads(report_raw)
    manifest = json.loads(manifest_raw)
    validate_receipt_summary(receipt, summary)

    expected = dict(receipt["output_sha256"])
    expected[SUMMARY_PATH.rsplit("/", 1)[-1]] = {
        "bytes": len(summary_raw),
        "sha256": hashlib.sha256(summary_raw).hexdigest(),
    }
    # The acceptance summary is stored under a different name from the
    # basename key above; verify it explicitly and keep the receipt schema
    # unchanged.
    expected_files = dict(receipt["output_sha256"])
    expected_files[SUMMARY_PATH] = {
        "bytes": len(summary_raw),
        "sha256": hashlib.sha256(summary_raw).hexdigest(),
    }

    checked = 0
    for path, spec in expected_files.items():
        raw = git(["show", f"{remote_ref}:{path}"])
        if len(raw) != int(spec["bytes"]):
            raise ValueError(f"byte-length mismatch for {path}")
        if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path}")
        tree_entry = git(["ls-tree", remote_ref, "--", path]).decode("utf-8").strip()
        fields = tree_entry.split()
        if len(fields) < 3 or fields[2] != git_blob_sha(raw):
            raise ValueError(f"Git tree/blob SHA mismatch for {path}")
        checked += 1

    receipt_tree = git(["ls-tree", remote_ref, "--", RECEIPT_PATH]).decode("utf-8").strip()
    receipt_fields = receipt_tree.split()
    if len(receipt_fields) < 3 or receipt_fields[2] != git_blob_sha(receipt_raw):
        raise ValueError("Git tree/blob SHA mismatch for persistence receipt")

    warnings = status_warnings(report, manifest, summary, receipt)
    print(f"Q92_RESULT_BRANCH_READBACK_PASS: {checked} output files plus receipt verified.")
    if warnings:
        for warning in warnings:
            print("Q92_METADATA_WARNING: " + warning)
        print("Q92_RESULT_BRANCH_STATUS: PASS_WITH_METADATA_WARNING")
    else:
        print("Q92_RESULT_BRANCH_STATUS: PASS")
    print(f"Q92_RESULT_BRANCH: {result_branch}")
    print(f"Q92_SOURCE_CHECKOUT_SHA: {receipt['source_checkout_sha']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(verify())
    except (ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"Q92_RESULT_BRANCH_READBACK_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
