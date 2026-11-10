#!/usr/bin/env python3
"""Refresh only the append-only position shadow and Q60 gate, not historical model fits."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB_PATH = ROOT / "scripts" / "sonar_position_regime_residual_lab.py"
ARCHIVE_PATH = ROOT / "data" / "storico_daily.csv"

spec = importlib.util.spec_from_file_location("sonar_position_regime_residual_lab", LAB_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("Q60 UPDATE BLOCKED: cannot import the registered position lab")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

with ARCHIVE_PATH.open(newline="", encoding="utf-8-sig") as handle:
    archive = list(csv.DictReader(handle))
dates = [row["data"] for row in archive]
draws = [[int(row[f"n{i}"]) for i in range(1, 6)] for row in archive]
if dates[-1] != "2026-11-10" or draws[-1] != [1, 7, 11, 22, 25]:
    raise SystemExit("Q60 UPDATE BLOCKED: canonical archive does not end with official contest 314")

shadow_result = lab.update_position_shadow(dates, draws)
gate = shadow_result["promotion_gate"]
if gate.get("valid_complete_prospective_targets") != 23:
    raise SystemExit("Q60 UPDATE BLOCKED: expected 23 complete paired targets, got " +
                     str(gate.get("valid_complete_prospective_targets")))
if gate.get("promotion_allowed") is not False or gate.get("missing_freezes_reconstructed") != 0:
    raise SystemExit("Q60 UPDATE BLOCKED: promotion or freeze-reconstruction guardrail changed")

report_path = lab.OUT / "position_regime_residual_lab.json"
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["prospective_shadow"] = shadow_result
    report["prospective_shadow_data_through"] = dates[-1]
    report["prospective_shadow_refresh_mode"] = (
        "Append-only prospective ledger refresh; historical full-history position metrics "
        "remain pinned to their last full model run."
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(json.dumps({
    "status": shadow_result["status"],
    "position_shadow_rows": shadow_result["rows"],
    "position_pending": shadow_result["pending"],
    "position_evaluated": shadow_result["evaluated"],
    "q60_complete_pairs": gate["valid_complete_prospective_targets"],
    "q60_remaining": gate["minimum_required"] - gate["valid_complete_prospective_targets"],
    "promotion_allowed": gate["promotion_allowed"],
    "missing_freezes_reconstructed": gate["missing_freezes_reconstructed"],
    "latest_position_freeze": shadow_result["latest_freeze"]
}, ensure_ascii=False))
