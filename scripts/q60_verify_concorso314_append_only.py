#!/usr/bin/env python3
"""Verify append-only evaluation of official VinciCasa contest 314."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
DATE = "2026-11-10"
ACTUAL = [1, 7, 11, 22, 25]
ACTUAL_TEXT = "1 7 11 22 25"

EXPECTED = {
    "freq_100": {
        "frozen_at": "2026-11-10T10:53:16+01:00",
        "history_cutoff": "2026-11-09",
        "top20": [26,16,25,36,10,12,15,28,29,38,1,5,9,17,18,30,34,37,39,24],
    },
    "APP::SONAR_HYBRID_RECENCY_ANALOG_FULL_HISTORY": {
        "frozen_at": "2026-11-10T10:53:16+01:00",
        "history_cutoff": "2026-11-09",
        "top20": [25,16,38,36,17,26,12,28,9,27,10,34,37,1,8,39,13,15,20,30],
    },
}
POSITION_EXPECTED = {
    "frozen_at": "2026-11-10T10:55:31+01:00",
    "history_cutoff": "2026-11-09",
    "top20": [26,16,36,12,15,29,38,1,17,37,39,3,23,2,25,10,28,5,9,18],
}

def check(condition, message, checks):
    checks.append({"check": message, "status": "PASS" if condition else "FAIL"})
    if not condition:
        raise SystemExit("Q60-D314 VALIDATION FAILED: " + message)

def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def nums(value):
    return [int(x) for x in str(value or "").split() if x]

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def one(rows, **criteria):
    matches = [row for row in rows if all(row.get(k) == v for k, v in criteria.items())]
    if len(matches) != 1:
        raise SystemExit("Q60-D314 VALIDATION FAILED: expected exactly one row for " + repr(criteria) + ", found " + str(len(matches)))
    return matches[0]

def metrics_for(top20):
    hits = sorted(set(top20) & set(ACTUAL))
    return {
        "top5_hits": len(set(top20[:5]) & set(ACTUAL)),
        "top10_hits": len(set(top20[:10]) & set(ACTUAL)),
        "top20_hits": len(hits),
        "hit_numbers": hits,
        "top20_5of5": len(hits) == 5,
    }

def main():
    checks = []
    archive_path = ROOT / "data" / "storico_daily.csv"
    archive = read_csv(archive_path)
    check(len(archive) == 3404, "canonical archive contains 3404 draws", checks)
    check(archive[-1] == {"data": DATE, "n1": "1", "n2": "7", "n3": "11", "n4": "22", "n5": "25"},
          "official contest 314 is appended as the final canonical row", checks)
    check(archive[-2]["data"] == "2026-11-09", "previous canonical row remains 2026-11-09", checks)

    data = read_json(ROOT / "src" / "data.json")
    check(data.get("histN") == 3404 and data.get("lastDate") == DATE,
          "generated app data reconciles to the 3404-row archive", checks)
    check(data.get("modelDraws", [])[-1] == {"d": DATE, "n": ACTUAL},
          "generated modelDraws includes the official target exactly", checks)

    global_rows = read_csv(OUT / "shadow_forecasts.csv")
    rows10 = [r for r in global_rows if r.get("target_date") == DATE]
    check(len(rows10) == 43, "all 43 pre-existing global/app freezes for 10 November are present", checks)
    check(all(r.get("status") == "EVALUATED" for r in rows10),
          "all 43 pre-existing global/app freezes were evaluated without reconstruction", checks)
    check(all(r.get("actual_numbers") == ACTUAL_TEXT for r in rows10),
          "all 43 evaluated freezes reconcile to the official result", checks)

    evaluated = {}
    for config_id, expected in EXPECTED.items():
        row = one(global_rows, target_date=DATE, config_id=config_id)
        top20 = nums(row["top20"])
        check(row["frozen_at"] == expected["frozen_at"], config_id + " frozen_at is unchanged", checks)
        check(row["history_cutoff"] == expected["history_cutoff"], config_id + " cutoff remains 2026-11-09", checks)
        check(top20 == expected["top20"], config_id + " frozen Top20 list is unchanged", checks)
        check(row["status"] == "EVALUATED" and row["actual_numbers"] == ACTUAL_TEXT,
              config_id + " is evaluated against the official result", checks)
        observed = metrics_for(top20)
        check(nums(row["hit_numbers"]) == observed["hit_numbers"], config_id + " hit numbers reconcile", checks)
        check(int(row["hit_count"]) == observed["top20_hits"], config_id + " Top20 hit count reconciles", checks)
        check(row["all5_top20"] == ("1" if observed["top20_5of5"] else "0"),
              config_id + " Top20 5/5 indicator reconciles", checks)
        check(row["evaluated_at_data_through"] == DATE,
              config_id + " evaluation cutoff is the official target date", checks)
        evaluated[config_id] = {
            "frozen_at": row["frozen_at"],
            "history_cutoff": row["history_cutoff"],
            "top20": top20,
            **observed
        }

    position_rows = read_csv(OUT / "position_mix_shadow.csv")
    position_row = one(position_rows, target_date=DATE, config_id="position_seed_mix_top20_v1")
    check(position_row["status"] == "EVALUATED" and position_row["actual_numbers"] == ACTUAL_TEXT,
          "position-seed freeze for 10 November is evaluated", checks)
    check(position_row["frozen_at"] == POSITION_EXPECTED["frozen_at"],
          "position-seed frozen_at is unchanged", checks)
    check(position_row["history_cutoff"] == "2026-11-09",
          "position-seed cutoff remains prior-day", checks)
    check(nums(position_row["top20"]) == POSITION_EXPECTED["top20"],
          "position-seed Top20 is unchanged", checks)
    position_metrics = metrics_for(nums(position_row["top20"]))
    check(nums(position_row["hit_numbers"]) == position_metrics["hit_numbers"] and
          int(position_row["hit_count"]) == position_metrics["top20_hits"] and
          position_row["all5_top20"] == "0",
          "position-seed hit ledger is internally consistent", checks)

    gate = read_json(OUT / "prospective_promotion_gate.json")
    check(gate.get("valid_complete_prospective_targets") == 23,
          "Q60 advances from 22 to 23 complete prospective paired targets", checks)
    check(DATE in gate.get("paired_target_dates", []),
          "10 November is included in the paired Q60 cohort", checks)
    check(gate.get("status") == "INSUFFICIENT_PROSPECTIVE_CASES" and
          gate.get("minimum_required") == 200 and gate.get("promotion_allowed") is False,
          "Q60 remains insufficient and promotion remains prohibited", checks)
    check(gate.get("missing_freezes_reconstructed") == 0,
          "no missing historical freeze was reconstructed", checks)
    check(gate.get("position_top20_5of5") == 0 and gate.get("global_top20_5of5") == 1,
          "paired Top20 5/5 counts remain 0 position vs 1 global", checks)
    check(gate.get("mcnemar_exact_two_sided_p") == 1.0,
          "paired exact McNemar test remains non-significant", checks)

    metrics = read_json(OUT / "latest_metrics.json")
    check(metrics.get("data_last_date") == DATE and metrics.get("total_draws") == 3404,
          "sequence-agent metrics use the official 3404-draw cutoff", checks)
    check(metrics.get("shadow_forecasts_pending") == 42 and
          metrics.get("shadow_forecasts_evaluated") == 1235 and
          metrics.get("shadow_forecasts_total") == 1277,
          "global shadow counts reconcile after evaluating 10 November and freezing 42 next-day rules", checks)

    next_global = one(global_rows, target_date="2026-11-11", config_id="freq_100")
    check(next_global["status"] == "FROZEN_PENDING" and next_global["history_cutoff"] == DATE,
          "next global freq_100 freeze is pending with 10 November as cutoff", checks)
    next_position = one(position_rows, target_date="2026-11-11", config_id="position_seed_mix_top20_v1")
    check(next_position["status"] == "FROZEN_PENDING" and next_position["history_cutoff"] == DATE,
          "next position-seed freeze is pending with 10 November as cutoff", checks)

    active = read_json(OUT / "active_engine_walkforward.json")
    current = active.get("current_frozen_forecast", {})
    check(current.get("target_date") == DATE and current.get("status") == "EVALUATED",
          "exact-source active app freeze for 10 November is evaluated", checks)
    check(current.get("history_cutoff") == "2026-11-09" and
          current.get("exact_top20_matches_committed_ui") is True,
          "active app freeze preserves its prior-day cutoff and exact-source reconciliation", checks)

    queue = read_json(OUT / "research_queue_status.json")
    q60 = next((x for x in queue.get("tasks", []) if x.get("id") == "Q60"), {})
    check(queue.get("overall_cycle_status") == "INCOMPLETE" and
          q60.get("status") == "INSUFFICIENT_PROSPECTIVE_CASES",
          "research queue remains incomplete at the registered Q60 gate", checks)
    check(any("23 complete prospective paired targets" in e for e in q60.get("validation_errors", [])),
          "queue explicitly records 23/200 and the remaining evidence requirement", checks)

    result = {
        "experiment_id": "Q60-D314-APPEND-ONLY",
        "status": "PASS",
        "date": DATE,
        "contest_number": 314,
        "official_result": ACTUAL,
        "checks_passed": len(checks),
        "checks_failed": 0,
        "checks": checks,
        "paired_target": {
            "global_freq_100": evaluated["freq_100"],
            "position_seed_mix_top20_v1": {
                "frozen_at": position_row["frozen_at"],
                "history_cutoff": position_row["history_cutoff"],
                "top20": nums(position_row["top20"]),
                **position_metrics
            },
            "active_app_engine": evaluated["APP::SONAR_HYBRID_RECENCY_ANALOG_FULL_HISTORY"],
            "position_minus_global_top20_hits": position_metrics["top20_hits"] - evaluated["freq_100"]["top20_hits"],
            "position_minus_global_top20_5of5": int(position_metrics["top20_5of5"]) - int(evaluated["freq_100"]["top20_5of5"])
        },
        "q60": {
            "complete_paired_targets": gate["valid_complete_prospective_targets"],
            "required": gate["minimum_required"],
            "remaining": gate["minimum_required"] - gate["valid_complete_prospective_targets"],
            "promotion_allowed": gate["promotion_allowed"],
            "missing_freezes_reconstructed": gate["missing_freezes_reconstructed"],
            "paired_exact_mcnemar_p": gate["mcnemar_exact_two_sided_p"],
            "position_top20_5of5": gate["position_top20_5of5"],
            "global_top20_5of5": gate["global_top20_5of5"],
            "paired_rate_difference": gate["paired_rate_difference_position_minus_global"],
            "paired_rate_difference_95_ci": gate["paired_rate_difference_95_ci"]
        },
        "next_target_freezes": {
            "global_freq_100_2026_11_11": {
                "status": next_global["status"],
                "history_cutoff": next_global["history_cutoff"],
                "frozen_at": next_global["frozen_at"],
                "top20": nums(next_global["top20"])
            },
            "position_seed_mix_2026_11_11": {
                "status": next_position["status"],
                "history_cutoff": next_position["history_cutoff"],
                "frozen_at": next_position["frozen_at"],
                "top20": nums(next_position["top20"])
            }
        },
        "source_sha256": {
            "archive": sha256(archive_path),
            "global_shadow": sha256(OUT / "shadow_forecasts.csv"),
            "position_shadow": sha256(OUT / "position_mix_shadow.csv"),
            "gate": sha256(OUT / "prospective_promotion_gate.json"),
            "active_engine": sha256(OUT / "active_engine_walkforward.json")
        },
        "limitations": [
            "This is one additional prospective paired target, not a validation sample sufficient for promotion.",
            "The primary Q60 endpoint remains Top20 5/5; this target is a tie on that binary endpoint.",
            "Top5/Top10/Top20 hit counts are descriptive for this single target.",
            "No model parameters, candidate lists or historical freezes were changed."
        ],
        "next_action": "Continue append-only paired evaluation; 177 complete prospective pairs remain before the registered 200-case gate."
    }
    (OUT / "q60_concorso314_append_only_validation_2026-11-10.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checkpoint = [
        "# Q60 — official contest 314 append-only checkpoint",
        "",
        "- Official result: **1, 7, 11, 22, 25**.",
        "- Canonical archive: **3404 draws**, cutoff **2026-11-10**.",
        "- Existing global, position-seed and exact app freezes preserve their original Top20 lists, timestamps and 2026-11-09 cutoffs.",
        "- Global freq_100: Top5/Top10/Top20 hits **1/1/2**.",
        "- Position seed mix: Top5/Top10/Top20 hits **0/1/2**.",
        "- Exact app engine: Top5/Top10/Top20 hits **1/1/2**.",
        "- Q60: **23/200** complete paired targets; **177 remaining**.",
        "- Top20 5/5: position **0**, global **1**; this target is a tie (both 0/5), so the paired exact McNemar result remains non-significant.",
        "- Missing freezes reconstructed: **0**; promotion allowed: **false**.",
        "- Next target freezes for 2026-11-11 are pending with 2026-11-10 cutoff for freq_100 and position seed mix.",
        "",
        "## Decision",
        "Keep the model exploratory. Do not tune from this single target; continue the 200-pair prospective gate."
    ]
    (OUT / "q60_concorso314_append_only_checkpoint_2026-11-10.md").write_text(
        "\n".join(checkpoint) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "PASS",
        "checks": len(checks),
        "q60_pairs": gate["valid_complete_prospective_targets"],
        "remaining": gate["minimum_required"] - gate["valid_complete_prospective_targets"],
        "archive_sha256": result["source_sha256"]["archive"]
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
