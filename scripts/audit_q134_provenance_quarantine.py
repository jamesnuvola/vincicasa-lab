#!/usr/bin/env python3
"""Q134: detect source-provenance contamination without rewriting forecasts."""
from __future__ import annotations
import csv, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-11-11"
NEXT_DATE = "2026-11-12"
NUMBERS = "1 21 22 27 29"
MAIN_COMMIT = "0bf1ef0d39afb671ff83e519489f16b0c24eb15a"
REPORT = "reports/data_quality/q134_provenance_quarantine_audit_2026-11-12.json"
VALIDATION = "reports/data_quality/q134_provenance_quarantine_validation_2026-11-12.json"
MANIFEST = "reports/data_quality/q134_provenance_quarantine_manifest_2026-11-12.json"
SOURCES = {
 "data/storico_daily.csv": ("fcb453ed06c8002314f826dbac79d6935f9ac103", 88172),
 "reports/sequence_agent/latest_metrics.json": ("c1cd3b6e0bc1caff0ddebdc9fd5dbac14c0fb95a", 113405),
 "reports/sequence_agent/active_engine_walkforward.json": ("2a89a403d955561f6c6697e5b422146439ff7001", 17396),
 "reports/sequence_agent/shadow_forecasts.csv": ("ac69059506bc79fbc6999e21ec6cd9636431afbc", 354671),
 "reports/sequence_agent/position_mix_shadow.csv": ("6af73133802571f9352e647a7b1e1db2eb76ed4c", 9341),
 "reports/sequence_agent/prospective_promotion_gate.json": ("330a7749e82c7c53fc8b7748804bc389a85dddb6", 2015),
 "reports/sequence_agent/research_queue_status.json": ("77eb2081800a34682441e7c504dcbc53bbdd757e", 4947),
}

def fail(message):
 raise RuntimeError("Q134 AUDIT FAILED: " + message)

def git_blob_sha(data):
 return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def read_bytes(relative):
 return (ROOT / relative).read_bytes()

def read_json(relative):
 return json.loads(read_bytes(relative).decode("utf-8"))

def read_csv(relative):
 with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
  return list(csv.DictReader(handle))

def verify_sources():
 for relative, (expected_sha, expected_bytes) in SOURCES.items():
  data = read_bytes(relative)
  if git_blob_sha(data) != expected_sha:
   fail("source blob changed: " + relative)
  if len(data) != expected_bytes:
   fail("source byte length changed: " + relative)

def verify_manifest():
 manifest = read_json(MANIFEST)
 entries = manifest.get("entries")
 if not isinstance(entries, list) or not entries:
  fail("manifest entries missing")
 for entry in entries:
  data = read_bytes(entry["path"])
  if git_blob_sha(data) != entry["git_blob_sha"]:
   fail("manifest SHA mismatch: " + entry["path"])
  if len(data) != entry["utf8_bytes"]:
   fail("manifest byte mismatch: " + entry["path"])
 return len(entries)

def verify_state():
 archive = read_csv("data/storico_daily.csv")
 rows = [r for r in archive if r["data"] == DATE]
 if len(rows) != 1:
  fail("expected exactly one canonical 315 row")
 actual = " ".join(rows[0][f"n{i}"] for i in range(1, 6))
 if actual != NUMBERS:
  fail("unexpected canonical 315 row: " + actual)

 metrics = read_json("reports/sequence_agent/latest_metrics.json")
 if (metrics.get("total_draws"), metrics.get("data_last_date"), metrics.get("walk_forward_targets_evaluated")) != (3405, DATE, 3205):
  fail("latest_metrics does not match the pinned 3,405-draw / 3,205-target state")

 active = read_json("reports/sequence_agent/active_engine_walkforward.json")
 data = active.get("data", {})
 if (data.get("total_draws"), data.get("last_date"), data.get("walk_forward_targets")) != (3405, DATE, 3205):
  fail("active-engine summary does not include the disputed 315 row")
 oos = active.get("splits", {}).get("oos", {})
 if (oos.get("targets"), oos.get("last_target")) != (641, DATE):
  fail("active-engine OOS boundary mismatch")
 freeze_rows = active.get("freeze_reconciliation", {}).get("rows", [])
 app315 = [r for r in freeze_rows if r.get("target_date") == DATE]
 app316 = [r for r in freeze_rows if r.get("target_date") == NEXT_DATE]
 if len(app315) != 1 or app315[0].get("status") != "EVALUATED" or app315[0].get("stored_actual_numbers") != [1,21,22,27,29]:
  fail("APP 315 freeze mismatch")
 if len(app316) != 1 or app316[0].get("status") != "FROZEN_PENDING" or app316[0].get("history_cutoff") != DATE:
  fail("APP 316 freeze mismatch")

 global_rows = read_csv("reports/sequence_agent/shadow_forecasts.csv")
 g315 = [r for r in global_rows if r["target_date"] == DATE]
 g316 = [r for r in global_rows if r["target_date"] == NEXT_DATE]
 if len(g315) != 43 or any(r["status"] != "EVALUATED" for r in g315):
  fail("expected 43 evaluated global rows for 315")
 if any(r["actual_numbers"] != NUMBERS or r["history_cutoff"] != "2026-11-10" for r in g315):
  fail("global 315 outcome/cutoff mismatch")
 if len(g316) != 43 or any(r["status"] != "FROZEN_PENDING" or r["history_cutoff"] != DATE for r in g316):
  fail("expected 43 pending global 316 freezes on disputed cutoff")

 positional = read_csv("reports/sequence_agent/position_mix_shadow.csv")
 p315 = [r for r in positional if r["target_date"] == DATE]
 p316 = [r for r in positional if r["target_date"] == NEXT_DATE]
 if len(p315) != 1 or p315[0]["status"] != "EVALUATED" or p315[0]["actual_numbers"] != NUMBERS:
  fail("positional 315 row mismatch")
 if len(p316) != 1 or p316[0]["status"] != "FROZEN_PENDING" or p316[0]["history_cutoff"] != DATE:
  fail("positional 316 freeze mismatch")

 gate = read_json("reports/sequence_agent/prospective_promotion_gate.json")
 dates = gate.get("paired_target_dates", [])
 reported = gate.get("valid_complete_prospective_targets")
 if reported != 24 or DATE not in dates or len(dates) != 24:
  fail("promotion gate does not report 24 paired dates including 315")
 eligible = len([d for d in dates if d != DATE])
 if eligible != 23:
  fail("expected 23 provenance-eligible paired dates")

 return {
  "canonical_archive": {"rows": len(archive), "last_date": archive[-1]["data"], "provisional_315": actual},
  "latest_metrics": {"total_draws": metrics["total_draws"], "last_date": metrics["data_last_date"], "targets": metrics["walk_forward_targets_evaluated"]},
  "active_engine": {"targets": data["walk_forward_targets"], "oos_targets": oos["targets"], "oos_last_target": oos["last_target"]},
  "forecast_rows": {"global_315_evaluated": len(g315), "positional_315_evaluated": len(p315), "global_316_pending": len(g316), "positional_316_pending": len(p316)},
  "promotion_gate": {"reported_pairs": reported, "eligible_after_quarantine": eligible, "excluded_date": DATE},
  "next_target_history": {"target_date": NEXT_DATE, "cutoff": DATE, "source_verified": False, "eligible_for_clean_primary_evaluation": False},
 }

def main():
 verify_sources()
 observed = verify_state()
 report = read_json(REPORT)
 validation = read_json(VALIDATION)
 if report.get("source_commit") != MAIN_COMMIT or report.get("observed_state") != observed:
  fail("persisted report does not match recomputed repository state")
 if report.get("decision") != "PROVENANCE_QUARANTINE_REQUIRED":
  fail("unexpected report decision")
 checks = validation.get("checks", [])
 if len(checks) != 12 or any(not x.get("passed") for x in checks):
  fail("validation artifact must contain 12 passing detection checks")
 count = verify_manifest()
 print("Q134 PASS: provenance conflict reproduced; 24 reported Q60 pairs -> 23 eligible after one-date quarantine; 44 next-target freezes use unverified 315 history; manifest " + str(count) + "/" + str(count) + "; no repository data mutated.")

if __name__ == "__main__":
 try:
  main()
 except Exception as exc:
  print(str(exc), file=sys.stderr)
  raise SystemExit(1)
