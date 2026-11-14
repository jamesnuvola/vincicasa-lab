#!/usr/bin/env python3
"""Q141-A20 prior-only quantile-state audit."""
import argparse
import csv
import hashlib
import json
import math
import random
from datetime import date
from pathlib import Path

SOURCE = "reports/sequence_agent/q141_a19_residual_subspace_drift_2026-11-14_target_ledger.csv"
SOURCE_SHA = "5613d5176ed48dd63df186258a53039e65840555"
PREFIX = "q141_a20_drift_quantile_state_2026-11-14"
WINDOW = 400
QUANTILE = 0.75
MIN_STATE = 25
REPS = 20000
BLOCK = 20
SPLITS = ("discovery", "validation", "blind_oos")


def blob_sha(data):
    return hashlib.sha1(("blob " + str(len(data)) + chr(0)).encode() + data).hexdigest()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def avg(values):
    if not values:
        raise ValueError("empty values")
    return sum(values) / len(values)


def quantile(values, q=QUANTILE):
    ordered = sorted(values)
    return ordered[math.floor((len(ordered) - 1) * q)]


def forecast_at(drift, capture, t):
    if t < WINDOW or t >= len(drift) or len(drift) != len(capture):
        raise ValueError("invalid target window")
    x = drift[t-WINDOW:t]
    y = capture[t-WINDOW:t]
    threshold = quantile(x)
    high_now = drift[t] >= threshold
    selected = [y[i] for i in range(WINDOW) if (x[i] >= threshold) == high_now]
    high_count = sum(v >= threshold for v in x)
    fallback = len(selected) < MIN_STATE
    prediction = avg(y if fallback else selected)
    return {
        "prediction": min(1.0, max(0.0, prediction)),
        "threshold": threshold,
        "state": "high" if high_now else "low",
        "prior_high_count": high_count,
        "prior_low_count": WINDOW - high_count,
        "selected_count": len(selected),
        "fallback": fallback,
    }


def bootstrap_ci(values, seed, reps=REPS, block=BLOCK):
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(reps):
        total = 0.0
        count = 0
        while count < n:
            start = rng.randrange(n)
            take = min(block, n-count)
            for j in range(take):
                total += values[(start+j) % n]
            count += take
        samples.append(total/n)
    samples.sort()
    return [samples[math.floor(.025*(reps-1))], samples[math.floor(.975*(reps-1))]]


def signflip_p(values, seed, reps=REPS, block=BLOCK):
    sums = [sum(values[i:i+block]) for i in range(0, len(values), block)]
    observed = avg(values)
    rng = random.Random(seed)
    exceed = 0
    for _ in range(reps):
        total = sum(v if rng.getrandbits(1) else -v for v in sums)
        if total / len(values) >= observed:
            exceed += 1
    return (exceed + 1) / (reps + 1)


def holm(p_values):
    order = sorted(range(len(p_values)), key=lambda i: (p_values[i], i))
    result = [0.0] * len(p_values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(p_values)-rank)*p_values[index]))
        result[index] = running
    return result


def load_rows(path):
    raw = Path(path).read_bytes()
    if blob_sha(raw) != SOURCE_SHA:
        raise ValueError("pinned source blob mismatch")
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["strict_prior"].lower() != "true":
                raise ValueError("non strict-prior row")
            if date.fromisoformat(row["cutoff_date"]) >= date.fromisoformat(row["target_date"]):
                raise ValueError("cutoff is not before target")
            for key in ("target_index", "prior_draws"):
                row[key] = int(row[key])
            for key in ("drift", "capture", "model_prediction", "baseline_mean400", "baseline_mean20"):
                row[key] = float(row[key])
                if not math.isfinite(row[key]):
                    raise ValueError("non-finite source value")
            rows.append(row)
    if len(rows) != 2186:
        raise ValueError("source row count mismatch")
    if [r["target_index"] for r in rows] != list(range(1201, 3387)):
        raise ValueError("target index sequence mismatch")
    counts = {s: sum(r["split"] == s for r in rows) for s in SPLITS}
    if counts != {"discovery": 1311, "validation": 437, "blind_oos": 438}:
        raise ValueError("split count mismatch")
    if rows[0]["target_date"] != "2020-10-30" or rows[-1]["target_date"] != "2026-10-24":
        raise ValueError("date range mismatch")
    return rows, raw


def run(source=SOURCE, out_dir="reports/sequence_agent"):
    rows, source_raw = load_rows(source)
    drift = [r["drift"] for r in rows]
    capture = [r["capture"] for r in rows]
    predictions = [None] * len(rows)
    metadata = [None] * len(rows)
    for t in range(WINDOW, len(rows)):
        metadata[t] = forecast_at(drift, capture, t)
        predictions[t] = metadata[t]["prediction"]

    results = {}
    tests = []
    ledger = []
    for si, split in enumerate(SPLITS):
        selected = [(i, r) for i, r in enumerate(rows) if r["split"] == split and predictions[i] is not None]
        actual = [r["capture"] for _, r in selected]
        pred = [predictions[i] for i, _ in selected]
        base = [r["baseline_mean400"] for _, r in selected]
        a19 = [r["model_prediction"] for _, r in selected]
        g_base = [(y-b)**2-(y-p)**2 for y,b,p in zip(actual,base,pred)]
        g_a19 = [(y-a)**2-(y-p)**2 for y,a,p in zip(actual,a19,pred)]
        p_base = signflip_p(g_base, 1419301 + si*100)
        p_a19 = signflip_p(g_a19, 1419302 + si*100)
        tests.extend([
            {"key": split+"_mse_gain_vs_mean400", "p_raw": p_base},
            {"key": split+"_mse_gain_vs_a19_ols", "p_raw": p_a19},
        ])
        hi = [r["capture"] for i,r in selected if metadata[i]["state"] == "high"]
        lo = [r["capture"] for i,r in selected if metadata[i]["state"] == "low"]
        results[split] = {
            "targets": len(selected),
            "first_target_date": selected[0][1]["target_date"],
            "last_target_date": selected[-1][1]["target_date"],
            "high_state_targets": len(hi),
            "high_state_rate": len(hi)/len(selected),
            "low_state_targets": len(lo),
            "fallback_targets": sum(metadata[i]["fallback"] for i,_ in selected),
            "mean_prior_q75_threshold": avg([metadata[i]["threshold"] for i,_ in selected]),
            "mean_capture": avg(actual),
            "mean_capture_high_state": avg(hi),
            "mean_capture_low_state": avg(lo),
            "high_minus_low_capture_descriptive": avg(hi)-avg(lo),
            "mse_gain_vs_mean400": avg(g_base),
            "mse_gain_vs_mean400_block20_ci95": bootstrap_ci(g_base, 1419303+si*100),
            "p_signflip_vs_mean400_raw": p_base,
            "mse_gain_vs_a19_ols": avg(g_a19),
            "mse_gain_vs_a19_ols_block20_ci95": bootstrap_ci(g_a19, 1419304+si*100),
            "p_signflip_vs_a19_ols_raw": p_a19,
            "mae_gain_vs_mean400_descriptive": avg([abs(y-b)-abs(y-p) for y,b,p in zip(actual,base,pred)]),
            "mse_mean400": avg([(y-b)**2 for y,b in zip(actual,base)]),
            "mse_a19_ols": avg([(y-a)**2 for y,a in zip(actual,a19)]),
            "mse_q75_state": avg([(y-p)**2 for y,p in zip(actual,pred)]),
        }
        for i, r in selected:
            m = metadata[i]
            ledger.append({
                "split": split, "target_index": r["target_index"], "target_date": r["target_date"],
                "cutoff_date": r["cutoff_date"], "prior_draws": r["prior_draws"],
                "drift": "%.12f" % r["drift"], "prior_q75_threshold": "%.12f" % m["threshold"],
                "current_state": m["state"], "prior_high_count": m["prior_high_count"],
                "prior_low_count": m["prior_low_count"], "selected_state_count": m["selected_count"],
                "fallback_to_prior_mean": str(m["fallback"]).lower(),
                "capture_response": "%.12f" % r["capture"],
                "q75_state_prediction": "%.12f" % m["prediction"],
                "baseline_mean400": "%.12f" % r["baseline_mean400"],
                "a19_linear_prediction": "%.12f" % r["model_prediction"],
                "mse_gain_vs_mean400": "%.12f" % ((r["capture"]-r["baseline_mean400"])**2-(r["capture"]-m["prediction"])**2),
                "mse_gain_vs_a19_ols": "%.12f" % ((r["capture"]-r["model_prediction"])**2-(r["capture"]-m["prediction"])**2),
                "strict_prior": "true",
            })

    adjusted = holm([x["p_raw"] for x in tests])
    for item, value in zip(tests, adjusted):
        item["p_holm"] = value
    lookup = {x["key"]: x for x in tests}
    primary_pass = all(
        results[s]["mse_gain_vs_mean400"] >= .001
        and results[s]["mse_gain_vs_mean400_block20_ci95"][0] > 0
        and lookup[s+"_mse_gain_vs_mean400"]["p_holm"] < .05
        for s in ("validation", "blind_oos")
    )
    decision = "DRIFT_Q75_STATE_CAPTURE_SKILL_CONFIRMED_EXPLORATORY" if primary_pass else "DRIFT_Q75_STATE_CAPTURE_SKILL_NOT_CONFIRMED"

    probe = 900
    original = forecast_at(drift, capture, probe)["prediction"]
    changed_drift = list(drift)
    changed_capture = list(capture)
    changed_capture[probe] = 1.0 - changed_capture[probe]
    for j in range(probe+1, len(rows)):
        changed_drift[j] = 1.0 - changed_drift[j]
        changed_capture[j] = 1.0 - changed_capture[j]
    invariant = original == forecast_at(changed_drift, changed_capture, probe)["prediction"]
    strict = all(r["strict_prior"].lower() == "true" and r["cutoff_date"] < r["target_date"] and r["prior_draws"] == r["target_index"] for r in rows)
    if not invariant or not strict:
        raise ValueError("leakage or temporal integrity failure")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = out / PREFIX
    ledger_path = Path(str(prefix) + "_target_ledger.csv")
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    report = {
        "schema_version": "1.0", "experiment_id": "Q141-A20",
        "status": "COMPLETED_HISTORICAL_PREQUENTIAL_NONLINEAR_DRIFT_AUDIT",
        "decision": decision,
        "hypothesis": {
            "primary": "A prior-only q75 residual-drift state and rolling 400-target conditional mean improve next-target structural-capture MSE by at least 0.001 versus prior-400 mean in Validation and historical Blind OOS, with positive block-bootstrap lower bounds and Holm-adjusted block-signflip p<0.05.",
            "quantile": QUANTILE, "window": WINDOW, "minimum_state_rows": MIN_STATE,
            "practical_mse_gain_threshold": 0.001, "primary_pass": primary_pass,
        },
        "source": {
            "experiment": "Q141-A19", "path": SOURCE,
            "git_blob_sha1": blob_sha(source_raw), "sha256": sha256(source_raw),
            "rows": len(rows), "first_target_date": rows[0]["target_date"],
            "last_target_date": rows[-1]["target_date"],
        },
        "design": {
            "source_rows": len(rows), "scored_rows": len(ledger),
            "first_400_discovery_rows_used_for_calibration_only": True,
            "split_counts_source": {"discovery": 1311, "validation": 437, "blind_oos": 438},
            "split_counts_scored": {s: results[s]["targets"] for s in SPLITS},
            "quantile_method": "lower order statistic floor((n-1)*0.75)",
            "state_rule": "current pre-target drift >= prior-400 drift q75 => high, else low",
            "training": "mean capture in matching prior state; fallback to prior-400 mean only if state count <25",
            "baselines": ["prior-400 rolling mean", "Q141-A19 prior-only linear drift OLS"],
            "bootstrap_replicates": REPS, "signflip_replicates": REPS, "block_length": BLOCK,
            "multiple_testing": "Holm across six one-sided MSE comparisons: three splits times two comparators",
        },
        "split_metrics": results, "registered_tests": tests,
        "integrity": {
            "pinned_source_git_blob_verified": blob_sha(source_raw) == SOURCE_SHA,
            "all_source_rows_strict_prior": strict,
            "target_response_and_future_suffix_mutation_invariant": invariant,
            "fixed_quantile_and_window_no_tuning": True,
            "replay_byte_identity": "PENDING_DEDICATED_CI",
        },
        "interpretation": "Q141-A20 forecasts a structural capture response, not candidate numbers or an exact quintet. Historical Blind OOS is exposed exploratory evidence, not virgin prospective confirmation.",
        "limitations": [
            "q75 was selected as one nonlinear diagnostic after reviewing A19; historical holdouts are not virgin evidence.",
            "A19 source panel ends 2026-10-24 and is separate from main through 2026-11-13.",
            "The rolling windows overlap; block methods use length 20 and sign-flip assumes approximate block-level symmetry.",
            "State frequency varies with the drift distribution; high/low is a relative rolling state, not a fixed physical regime.",
            "Structural capture is not exact-ticket accuracy or probability of winning.",
            "No production engine, canonical archive, forecast freeze, Q60 gate, or protected PR is modified.",
        ],
        "next_action": "Keep research-only. Do not tune additional thresholds on this panel; freeze a prospective drift-state monitor unchanged or retire this predictor family.",
    }
    report_path = Path(str(prefix) + "_report.json")
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Q141-A20 — Drift Quantile-State Capture Audit", "",
        "**Decision:** " + decision, "", "## Method", "",
        "- Pinned source: Q141-A19 ledger; Git blob " + blob_sha(source_raw) + ".",
        "- Rolling window: 400; current state threshold: prior-only q75.",
        "- Prediction: prior-400 mean capture in the same high/low state; minimum state count 25.",
        "- First 400 Discovery rows are calibration-only.", "",
        "## Results", "",
        "| Split | N | High N | High rate | Mean capture | MSE gain vs mean400 | 95% block CI | MSE gain vs A19 OLS | Holm p vs mean400 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in SPLITS:
        m = results[s]
        p = lookup[s+"_mse_gain_vs_mean400"]
        ci = m["mse_gain_vs_mean400_block20_ci95"]
        md.append("| %s | %d | %d | %.3f | %.6f | %.6f | [%.6f, %.6f] | %.6f | %.6f |" % (
            s, m["targets"], m["high_state_targets"], m["high_state_rate"], m["mean_capture"],
            m["mse_gain_vs_mean400"], ci[0], ci[1], m["mse_gain_vs_a19_ols"], p["p_holm"]))
    md += ["", "## Holm-corrected tests", "", "| Test | Raw p | Holm p |", "|---|---:|---:|"]
    for item in tests:
        md.append("| %s | %.6f | %.6f |" % (item["key"], item["p_raw"], item["p_holm"]))
    md += ["", "## Integrity", "",
           "- Source rows are strict-prior; cutoff dates precede target dates.",
           "- Each forecast uses 400 prior drift/capture pairs and current pre-target drift only.",
           "- Mutating target response and all later rows leaves the probe prediction unchanged.",
           "- Dedicated workflow performs tests, deterministic replay, and remote readback.", "",
           "## Limitations", ""]
    md.extend("- " + item for item in report["limitations"])
    md += ["", "## Next action", "", report["next_action"]]
    md_path = Path(str(prefix) + "_report.md")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    checkpoint = {
        "experiment_id": "Q141-A20", "status": "COMPUTED_PENDING_DEDICATED_CI",
        "decision": decision, "source_git_blob_sha1": blob_sha(source_raw),
        "source_rows": len(rows), "scored_rows": len(ledger),
        "split_counts_scored": {s: results[s]["targets"] for s in SPLITS},
        "replay_verified": False, "remote_readback": None,
        "next_action": "Run dedicated tests, deterministic replay, and remote Git readback.",
    }
    checkpoint_path = Path(str(prefix) + "_checkpoint.json")
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    protocol_path = Path("reports/sequence_agent/" + PREFIX + "_protocol.md")
    script_path = Path(__file__)
    paths = [report_path, md_path, ledger_path, checkpoint_path, protocol_path, script_path]
    manifest = {
        "experiment_id": "Q141-A20", "status": "COMPUTED_PENDING_DEDICATED_CI",
        "outputs": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p.read_bytes()), "git_blob_sha1": blob_sha(p.read_bytes())} for p in paths},
    }
    manifest_path = Path(str(prefix) + "_manifest.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    args = parser.parse_args()
    report = run(args.source, args.out_dir)
    print("A20_REPORT_READY " + json.dumps({
        "decision": report["decision"],
        "split_counts": report["design"]["split_counts_scored"],
        "blind_mse_gain_vs_mean400": report["split_metrics"]["blind_oos"]["mse_gain_vs_mean400"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
