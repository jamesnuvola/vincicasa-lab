#!/usr/bin/env python3
"""Persist accepted Q93 outputs append-only and verify exact Git object readback."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ.get("SONAR_BRANCH", "research/q93-spectral-coherence-20261110")
TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / ".q93-bundle"
PREFIX = "reports/sequence_agent/"
OUTPUT_NAMES = (
    "q93_spectral_coherence_catalog.jsonl",
    "q93_spectral_coherence_target_ledger.csv.gz",
    "q93_spectral_coherence_report.json",
    "q93_spectral_coherence_manifest.json",
    "q93_spectral_coherence_checkpoint_2026-11-10.md",
    "q93_spectral_coherence_validation.json",
)
PROTOCOL_NAME = "q93_spectral_coherence_protocol_2026-11-10.json"


def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            return json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed {exc.code}: {body[:2000]}") from exc


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    files = {name: (BUNDLE / name).read_bytes() for name in OUTPUT_NAMES}
    manifest = json.loads(files["q93_spectral_coherence_manifest.json"])
    validation = json.loads(files["q93_spectral_coherence_validation.json"])
    protocol_path = ROOT / "reports" / "sequence_agent" / PROTOCOL_NAME
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or manifest.get("status") != "ACCEPTANCE_PASS":
        raise SystemExit("Q93 persistence blocked: independent acceptance is not PASS")
    if validation.get("task_id") != "Q93-SPECTRAL-COHERENCE-01" or manifest.get("task_id") != validation.get("task_id"):
        raise SystemExit("Q93 persistence blocked: task identity mismatch")
    if protocol.get("task_id") != validation.get("task_id"):
        raise SystemExit("Q93 persistence blocked: protocol identity mismatch")

    metadata_names = {
        "catalog": OUTPUT_NAMES[0],
        "target_ledger": OUTPUT_NAMES[1],
        "report": OUTPUT_NAMES[2],
        "checkpoint": OUTPUT_NAMES[4],
        "validation": OUTPUT_NAMES[5],
        "protocol": PROTOCOL_NAME,
    }
    for key, name in metadata_names.items():
        meta = manifest.get("files", {}).get(key)
        data = protocol_path.read_bytes() if key == "protocol" else files[name]
        if not meta or meta.get("bytes") != len(data) or meta.get("sha256") != sha256(data):
            raise SystemExit("Q93 persistence blocked: manifest/artifact mismatch for " + key)

    ref_get = "/repos/" + REPO + "/git/ref/heads/" + urllib.parse.quote(BRANCH, safe="/")
    ref_patch = "/repos/" + REPO + "/git/refs/heads/" + urllib.parse.quote(BRANCH, safe="/")
    ref = api("GET", ref_get)
    parent = ref["object"]["sha"]
    parent_commit = api("GET", "/repos/" + REPO + "/git/commits/" + parent)
    base_tree = parent_commit["tree"]["sha"]

    entries = []
    blob_map = {}
    for name, data in files.items():
        path = PREFIX + name
        try:
            api("GET", "/repos/" + REPO + "/contents/" + urllib.parse.quote(path, safe="/")
                + "?ref=" + urllib.parse.quote(BRANCH, safe="/"))
        except RuntimeError as exc:
            if "failed 404" not in str(exc):
                raise
        else:
            raise SystemExit("Q93 append-only persistence blocked; path already exists: " + path)
        blob = api("POST", "/repos/" + REPO + "/git/blobs", {
            "content": base64.b64encode(data).decode("ascii"), "encoding": "base64"
        })
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        blob_map[path] = {"sha": blob["sha"], "bytes": len(data), "sha256": sha256(data)}

    tree = api("POST", "/repos/" + REPO + "/git/trees", {"base_tree": base_tree, "tree": entries})
    commit = api("POST", "/repos/" + REPO + "/git/commits", {
        "message": "Persist accepted Q93 spectral-coherence outputs [q93-results-persisted]",
        "tree": tree["sha"], "parents": [parent]
    })
    api("PATCH", ref_patch, {"sha": commit["sha"], "force": False})
    final_ref = api("GET", ref_get)
    if final_ref["object"]["sha"] != commit["sha"]:
        raise SystemExit("Q93 persistence blocked: branch head differs from created commit")

    for path, meta in blob_map.items():
        blob = api("GET", "/repos/" + REPO + "/git/blobs/" + meta["sha"])
        if blob.get("encoding") != "base64":
            raise SystemExit("Q93 unexpected Git blob encoding: " + path)
        readback = base64.b64decode(blob["content"])
        if len(readback) != meta["bytes"] or sha256(readback) != meta["sha256"]:
            raise SystemExit("Q93 exact-byte readback mismatch: " + path)

    result = {
        "status": "PERSISTED_AND_READBACK_VERIFIED",
        "parent_sha": parent,
        "persisted_head": commit["sha"],
        "files": blob_map,
        "acceptance": "PASS",
        "predictive_gate": validation.get("primary_gate", {}).get("status"),
    }
    print("SONAR_Q93_PERSISTENCE_BEGIN")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q93_PERSISTENCE_END")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("commit_sha=" + commit["sha"] + "\n")


if __name__ == "__main__":
    main()
