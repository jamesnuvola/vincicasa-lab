#!/usr/bin/env python3
"""Tolerance-aware PSR-04 cross-run verifier; exact double-run is checked by the Node script."""
import csv
import json
import re
import sys
from pathlib import Path

TOL = 1e-8
FINGERPRINT_PATHS = {
    ("integrity", "ledger_fingerprint_fnv1a32"),
    ("execution", "ledger_fingerprint_fnv1a32"),
}

def fnv1a32(text: str) -> str:
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"

def compare_json(a, b, path=()):
    if path in FINGERPRINT_PATHS:
        return
    if isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            raise AssertionError(f"JSON mismatch at {path}: {a!r} != {b!r}")
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > TOL:
            raise AssertionError(f"JSON numeric mismatch at {path}: {a!r} vs {b!r}")
        return
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            raise AssertionError(f"JSON key mismatch at {path}: {set(a) ^ set(b)}")
        for k in a:
            compare_json(a[k], b[k], path + (k,))
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise AssertionError(f"JSON length mismatch at {path}: {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            compare_json(x, y, path + (i,))
        return
    if a != b:
        raise AssertionError(f"JSON mismatch at {path}: {a!r} != {b!r}")

def compare_csv(expected_path: Path, actual_path: Path):
    with expected_path.open(newline="", encoding="utf-8") as f:
        expected = list(csv.reader(f))
    with actual_path.open(newline="", encoding="utf-8") as f:
        actual = list(csv.reader(f))
    if not expected or not actual or expected[0] != actual[0]:
        raise AssertionError("PSR-04 CSV header mismatch")
    if len(expected) != len(actual):
        raise AssertionError(f"PSR-04 CSV row count mismatch: {len(expected)} vs {len(actual)}")
    for row_idx, (er, ar) in enumerate(zip(expected, actual), start=1):
        if len(er) != len(ar):
            raise AssertionError(f"PSR-04 CSV column count mismatch at row {row_idx}")
        for col_idx, (ev, av) in enumerate(zip(er, ar), start=1):
            try:
                en, an = float(ev), float(av)
            except (ValueError, TypeError):
                if ev != av:
                    raise AssertionError(f"PSR-04 CSV text mismatch row={row_idx} col={col_idx}: {ev!r} != {av!r}")
            else:
                if abs(en - an) > TOL:
                    raise AssertionError(f"PSR-04 CSV numeric mismatch row={row_idx} col={col_idx}: {en} vs {an}")

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_psr04_artifact_reproducibility.py EXPECTED_DIR ACTUAL_DIR")
    expected_dir, actual_dir = map(Path, sys.argv[1:])
    names = ["PSR04_results_20261108.json", "PSR04_results_20261108.md", "PSR04_target_ledger_20261108.csv"]
    expected_json = json.loads((expected_dir / names[0]).read_text(encoding="utf-8"))
    actual_json = json.loads((actual_dir / names[0]).read_text(encoding="utf-8"))
    expected_csv = (expected_dir / names[2]).read_text(encoding="utf-8")
    actual_csv = (actual_dir / names[2]).read_text(encoding="utf-8")
    if fnv1a32(expected_csv) != expected_json["integrity"]["ledger_fingerprint_fnv1a32"]:
        raise AssertionError("Persisted PSR-04 report fingerprint does not match persisted ledger")
    if fnv1a32(actual_csv) != actual_json["integrity"]["ledger_fingerprint_fnv1a32"]:
        raise AssertionError("Fresh PSR-04 report fingerprint does not match fresh ledger")
    if actual_json.get("execution", {}).get("double_run_exact_match") is not True:
        raise AssertionError("PSR-04 Node internal double-run reproducibility check did not pass")
    compare_json(expected_json, actual_json)
    compare_csv(expected_dir / names[2], actual_dir / names[2])
    expected_md = (expected_dir / names[1]).read_text(encoding="utf-8")
    actual_md = (actual_dir / names[1]).read_text(encoding="utf-8")
    normalize = lambda s: re.sub(r"(FNV-1a32 )([0-9a-f]{8})", r"\1<FINGERPRINT>", s)
    if normalize(expected_md) != normalize(actual_md):
        raise AssertionError("PSR-04 Markdown differs beyond the ledger fingerprint")
    print(f"PSR-04 reproducibility PASS: JSON/CSV numeric tolerance={TOL:g}; exact internal double-run=true; rows={len(expected_csv.splitlines())-1}")

if __name__ == "__main__":
    main()
