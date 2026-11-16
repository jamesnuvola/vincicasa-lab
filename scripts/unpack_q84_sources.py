#!/usr/bin/env python3
"""Verify and unpack the registered Q84 source bundle into its plain-text paths."""
from __future__ import annotations
import hashlib, io, json, tarfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "research" / "q84_source_bundle_2026-11-16.tar.xz"
EXPECTED_SHA256 = "4c651dc11edbbf5adbfb92bb82023f6565cbf167995c7b728d3a1e7d04de3ce1"
EXPECTED_FILES = {
    "scripts/sonar_strategy_atlas.py",
    "scripts/validate_sonar_strategy_atlas.py",
    "scripts/persist_q84_outputs.py",
    "tests/test_sonar_strategy_atlas.py",
}
def main():
    raw=BUNDLE.read_bytes()
    observed=hashlib.sha256(raw).hexdigest()
    if observed!=EXPECTED_SHA256: raise SystemExit("Q84_UNPACK_BLOCKED: source bundle SHA-256 mismatch")
    extracted=set()
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:xz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name not in EXPECTED_FILES:
                raise SystemExit("Q84_UNPACK_BLOCKED: unexpected archive member "+member.name)
            if member.name in extracted: raise SystemExit("Q84_UNPACK_BLOCKED: duplicate archive member "+member.name)
            source=archive.extractfile(member)
            if source is None: raise SystemExit("Q84_UNPACK_BLOCKED: unreadable archive member "+member.name)
            destination=(ROOT/member.name).resolve()
            if ROOT.resolve() not in destination.parents: raise SystemExit("Q84_UNPACK_BLOCKED: path traversal rejected")
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(source.read())
            extracted.add(member.name)
    if extracted!=EXPECTED_FILES: raise SystemExit("Q84_UNPACK_BLOCKED: source bundle is incomplete")
    print(json.dumps({"status":"Q84_SOURCE_BUNDLE_VERIFIED","sha256":observed,"files":sorted(extracted)},separators=(",",":")))
if __name__=="__main__": main()
