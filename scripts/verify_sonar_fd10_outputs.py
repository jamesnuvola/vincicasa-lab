#!/usr/bin/env python3
"""Tolerance-aware readback check for the independently generated FD-10 outputs."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

TOL = 1e-12


def compare_json(expected, actual, path="$"):
    if isinstance(expected, bool) or isinstance(actual, bool):
        if type(expected) is not type(actual) or expected != actual:
            raise AssertionError(f"{path}: boolean/type mismatch {expected!r} != {actual!r}")
        return
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(float(expected), float(actual), rel_tol=0.0, abs_tol=TOL):
            raise AssertionError(f"{path}: numeric mismatch {expected!r} != {actual!r}")
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            raise AssertionError(f"{path}: key mismatch")
        for key in expected:
            compare_json(expected[key], actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise AssertionError(f"{path}: list length mismatch")
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare_json(left, right, f"{path}[{index}]")
        return
    if type(expected) is not type(actual) or expected != actual:
        raise AssertionError(f"{path}: value mismatch {expected!r} != {actual!r}")


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        raise AssertionError(f"{path}: empty CSV")
    return rows


def compare_csv(expected_path, actual_path):
    expected = read_csv(expected_path)
    actual = read_csv(actual_path)
    if len(expected) != len(actual):
        raise AssertionError("CSV row-count mismatch")
    if expected[0] != actual[0]:
        raise AssertionError("CSV header mismatch")
    for row_index, (left, right) in enumerate(zip(expected[1:], actual[1:]), start=2):
        if len(left) != len(right):
            raise AssertionError(f"CSV column-count mismatch at row {row_index}")
        for column_index, (a, b) in enumerate(zip(left, right), start=1):
            try:
                af = float(a)
                bf = float(b)
            except ValueError:
                if a != b:
                    raise AssertionError(
                        f"CSV text mismatch at row {row_index}, column {column_index}: {a!r} != {b!r}"
                    )
            else:
                if not math.isclose(af, bf, rel_tol=0.0, abs_tol=TOL):
                    raise AssertionError(
                        f"CSV numeric mismatch at row {row_index}, column {column_index}: {a!r} != {b!r}"
                    )


def main():
    expected_report, actual_report, expected_ledger, actual_ledger = sys.argv[1:5]
    with Path(expected_report).open(encoding="utf-8") as handle:
        expected = json.load(handle)
    with Path(actual_report).open(encoding="utf-8") as handle:
        actual = json.load(handle)
    compare_json(expected, actual)
    compare_csv(expected_ledger, actual_ledger)
    print("FD10_PERSISTED_REPORT_LEDGER_REPLAY_PASS")


if __name__ == "__main__":
    main()
