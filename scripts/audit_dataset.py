#!/usr/bin/env python3
"""Audit the VinciCasa source archive and generated app data.

Fails closed: the update workflow must not commit a malformed draw, duplicate
date, out-of-order archive, or JSON file inconsistent with the canonical CSV.
Uses only the Python standard library.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "storico_daily.csv")
JSON_PATH = os.path.join(BASE, "src", "data.json")
LO = (1, 2, 3, 4, 5)
HI = (36, 37, 38, 39, 40)


def fail(message):
    print(f"DATA AUDIT FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_csv():
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            expected = ["data", "n1", "n2", "n3", "n4", "n5"]
            if reader.fieldnames != expected:
                fail(f"CSV header must be {expected}; got {reader.fieldnames}")
            rows = list(reader)
    except OSError as exc:
        fail(f"cannot read {CSV_PATH}: {exc}")

    if not rows:
        fail("CSV contains no draws")

    seen = set()
    previous = None
    for line, row in enumerate(rows, start=2):
        raw_date = (row.get("data") or "").strip()
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            fail(f"line {line}: invalid ISO date {raw_date!r}")
        if raw_date in seen:
            fail(f"line {line}: duplicate draw date {raw_date}")
        if previous is not None and raw_date <= previous:
            fail(f"line {line}: dates are not strictly ascending ({previous}, {raw_date})")
        seen.add(raw_date)
        previous = raw_date

        try:
            nums = [int(row[f"n{i}"]) for i in range(1, 6)]
        except (TypeError, ValueError):
            fail(f"line {line}: missing or non-integer number")
        if len(set(nums)) != 5 or nums != sorted(nums):
            fail(f"line {line}: numbers must be five distinct ascending values: {nums}")
        for p, n in enumerate(nums):
            if not LO[p] <= n <= HI[p]:
                fail(f"line {line}: P{p + 1}={n} outside valid range {LO[p]}-{HI[p]}")
    return rows


def check_json(rows):
    try:
        with open(JSON_PATH, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid JSON at {JSON_PATH}: {exc}")

    last_date = rows[-1]["data"].strip()
    if payload.get("histN") != len(rows):
        fail(f"src/data.json histN={payload.get('histN')} but CSV has {len(rows)} rows")
    if payload.get("lastDate") != last_date:
        fail(f"src/data.json lastDate={payload.get('lastDate')} but CSV ends {last_date}")

    draws = payload.get("draws")
    if not isinstance(draws, list) or not draws:
        fail("src/data.json draws must be a non-empty array")
    for i, draw in enumerate(draws):
        d = draw.get("d")
        nums = draw.get("n")
        if not isinstance(d, str) or not isinstance(nums, list) or len(nums) != 5:
            fail(f"src/data.json draws[{i}] has invalid shape")
        try:
            date.fromisoformat(d)
        except ValueError:
            fail(f"src/data.json draws[{i}] has invalid date {d!r}")
        if len(set(nums)) != 5 or nums != sorted(nums):
            fail(f"src/data.json draws[{i}] has invalid numbers {nums}")
        if any(not isinstance(n, int) for n in nums):
            fail(f"src/data.json draws[{i}] contains a non-integer number")
        if any(not LO[p] <= nums[p] <= HI[p] for p in range(5)):
            fail(f"src/data.json draws[{i}] has a number outside its positional range")
    if draws[-1]["d"] != last_date:
        fail(f"app draws end at {draws[-1]['d']} but CSV ends at {last_date}")
    if any(draws[i]["d"] >= draws[i + 1]["d"] for i in range(len(draws) - 1)):
        fail("src/data.json draws are not strictly chronological")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-json", action="store_true",
                        help="also validate generated src/data.json against the CSV")
    args = parser.parse_args()
    rows = read_csv()
    if args.check_json:
        check_json(rows)
    print(f"DATA AUDIT OK: {len(rows)} draws, {rows[0]['data']} -> {rows[-1]['data']}"
          + ("; generated JSON consistent" if args.check_json else ""))


if __name__ == "__main__":
    main()
