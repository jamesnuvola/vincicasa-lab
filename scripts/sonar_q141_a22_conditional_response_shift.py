#!/usr/bin/env python3
"""Q141-A22: dependence-preserving audit of the Q75 state run and capture response."""
from __future__ import annotations
import argparse, csv, json, math, random
from datetime import date
from pathlib import Path

DATE = "2026-11-14"
PREFIX = f"q141_a22_conditional_response_shift_{DATE}"
EXPECTED_A20_ROWS = 1786
EXPECTED_A21_ROWS = 20
B = 20000
STATE_BLOCKS = (20, 50, 100, 200)
CAPTURE_BLOCKS = (5, 10, 20, 40)
SEED_BASE = 14122200


def read_csv(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def is_true(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def validate_temporal_rows(rows, expected_indices, state_key, gain_key):
    if len(rows) != len(expected_indices):
        raise ValueError("A22_BLOCKED: unexpected source row count")
    dates, normalized = [], []
    for row, expected_index in zip(rows, expected_indices):
        idx = int(row["target_index"])
        target, cutoff = date.fromisoformat(row["target_date"]), date.fromisoformat(row["cutoff_date"])
        if idx != expected_index:
            raise ValueError("A22_BLOCKED: target index sequence mismatch")
        if cutoff >= target or not is_true(row["strict_prior"]):
            raise ValueError("A22_BLOCKED: non-strict or unverified prior cutoff")
        if dates and target <= dates[-1]:
            raise ValueError("A22_BLOCKED: dates are not strictly increasing")
        dates.append(target)
        state = row[state_key].strip().lower()
        if state not in {"high", "low"}:
            raise ValueError("A22_BLOCKED: invalid state label")
        capture, gain = float(row["capture_response"]), float(row[gain_key])
        if not math.isfinite(capture) or not 0.0 <= capture <= 1.0 or not math.isfinite(gain):
            raise ValueError("A22_BLOCKED: non-finite response or gain")
        normalized.append({
            "target_index": idx, "target_date": row["target_date"], "cutoff_date": row["cutoff_date"],
            "state": 1 if state == "high" else 0, "capture": capture, "gain": gain,
            "split": row.get("split", "extension"), "drift": float(row.get("drift", "nan")),
            "prediction": float(row.get("q75_state_prediction", row.get("a20_q75_prediction", "nan"))),
            "a19_ols_prediction": float(row.get("a19_ols_prediction", "nan")),
            "baseline_mean400": float(row.get("baseline_mean400", "nan")),
            "baseline_mean20": float(row.get("baseline_mean20", "nan")),
            "source": "A20" if "split" in row else "A21",
        })
    return normalized


def validate_inputs(a20_rows, a21_rows):
    if len(a20_rows) != EXPECTED_A20_ROWS or len(a21_rows) != EXPECTED_A21_ROWS:
        raise ValueError("A22_BLOCKED: source dimensions do not match pinned A20/A21 ledgers")
    hist = validate_temporal_rows(a20_rows, range(1601, 3387), "current_state", "mse_gain_vs_mean400")
    ext = validate_temporal_rows(a21_rows, range(3387, 3407), "q75_state", "mse_gain_q75_vs_mean400")
    if hist[0]["target_date"] != "2021-12-04" or hist[-1]["target_date"] != "2026-10-24":
        raise ValueError("A22_BLOCKED: A20 source date range mismatch")
    if ext[0]["target_date"] != "2026-10-25" or ext[-1]["target_date"] != "2026-11-13":
        raise ValueError("A22_BLOCKED: A21 extension date range mismatch")
    if hist[-1]["target_index"] + 1 != ext[0]["target_index"]:
        raise ValueError("A22_BLOCKED: A20/A21 target index boundary mismatch")
    if date.fromisoformat(ext[0]["target_date"]) <= date.fromisoformat(hist[-1]["target_date"]):
        raise ValueError("A22_BLOCKED: extension does not follow historical source")
    return hist, ext


def longest_run(values):
    best = current = 0
    for value in values:
        if int(value) == 1:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def terminal_high_run(rows):
    if not rows or rows[-1]["state"] != 1:
        raise ValueError("A22_BLOCKED: historical terminal state is not high")
    start = len(rows) - 1
    while start >= 0 and rows[start]["state"] == 1:
        start -= 1
    return rows[start + 1:]


def acf(values, lag):
    x = [float(v) for v in values]
    mean = sum(x) / len(x)
    denominator = sum((v - mean) ** 2 for v in x)
    if denominator <= 1e-15 or lag >= len(x):
        return 0.0
    return sum((x[i] - mean) * (x[i - lag] - mean) for i in range(lag, len(x))) / denominator


def stationary_sample(values, sample_size, mean_block_length, rng):
    if not values or mean_block_length < 1:
        raise ValueError("A22_BLOCKED: invalid stationary bootstrap input")
    index, result = rng.randrange(len(values)), []
    for t in range(sample_size):
        if t and rng.random() < 1.0 / mean_block_length:
            index = rng.randrange(len(values))
        result.append(values[index])
        index = (index + 1) % len(values)
    return result


def linear_quantile(values, q):
    x = sorted(float(v) for v in values)
    if not x:
        raise ValueError("A22_BLOCKED: empty quantile input")
    pos, lo = (len(x) - 1) * q, int(math.floor((len(x) - 1) * q))
    hi = int(math.ceil((len(x) - 1) * q))
    return x[lo] if lo == hi else x[lo] * (hi - pos) + x[hi] * (pos - lo)


def holm_adjust(tests):
    order = sorted(range(len(tests)), key=lambda i: tests[i]["p_raw"])
    adjusted, running, n = [1.0] * len(tests), 0.0, len(tests)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (n - rank) * tests[idx]["p_raw"]))
        adjusted[idx] = running
    for idx, test in enumerate(tests):
        test["p_holm_12"] = adjusted[idx]
    return tests


def bootstrap_state_p(values, block_length, seed, observed_high):
    rng, stats, exceed = random.Random(seed), [], 0
    for _ in range(B):
        stat = sum(stationary_sample(values, 20, block_length, rng))
        stats.append(stat)
        if stat >= observed_high:
            exceed += 1
    return {"null_mean": sum(stats) / B,
            "null_ci95": [linear_quantile(stats, 0.025), linear_quantile(stats, 0.975)],
            "exceedances": exceed, "p_raw": (exceed + 1) / (B + 1)}


def bootstrap_capture_p(values, observed_mean, block_length, seed):
    rng, stats, lower = random.Random(seed), [], 0
    for _ in range(B):
        stat = sum(stationary_sample(values, 20, block_length, rng)) / 20.0
        stats.append(stat)
        if stat <= observed_mean:
            lower += 1
    return {"null_mean": sum(stats) / B,
            "null_ci95": [linear_quantile(stats, 0.025), linear_quantile(stats, 0.975)],
            "exceedances": lower, "p_raw": (lower + 1) / (B + 1)}


def moving_block_gain_ci(values, block_length=5, seed=14122405):
    rng, n, stats = random.Random(seed), len(values), []
    for _ in range(B):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n)
            for j in range(block_length):
                sample.append(values[(start + j) % n])
                if len(sample) == n:
                    break
        stats.append(sum(sample) / n)
    return [linear_quantile(stats, 0.025), linear_quantile(stats, 0.975)]


def split_summary(rows):
    result = {}
    for split in ("discovery", "validation", "blind_oos"):
        part = [r for r in rows if r["split"] == split]
        high = [r["capture"] for r in part if r["state"] == 1]
        low = [r["capture"] for r in part if r["state"] == 0]
        result[split] = {
            "targets": len(part), "high_targets": len(high),
            "high_rate": len(high) / len(part) if part else None,
            "longest_high_run": longest_run([r["state"] for r in part]),
            "mean_capture_high": sum(high) / len(high) if high else None,
            "mean_capture_low": sum(low) / len(low) if low else None,
            "high_minus_low_capture": (sum(high) / len(high) - sum(low) / len(low)) if high and low else None,
            "mean_q75_mse_gain_vs_mean400": sum(r["gain"] for r in part) / len(part) if part else None,
        }
    return result


def analyze(hist, ext):
    history_states = [r["state"] for r in hist]
    blind_states = [r["state"] for r in hist if r["split"] == "blind_oos"]
    terminal = terminal_high_run(hist)
    extension_states = [r["state"] for r in ext]
    extension_captures = [r["capture"] for r in ext]
    extension_gains = [r["gain"] for r in ext]
    observed_capture, observed_high = sum(extension_captures) / len(extension_captures), sum(extension_states)
    previous20_capture = sum(r["capture"] for r in terminal[-20:]) / 20.0
    terminal_capture = [r["capture"] for r in terminal]
    tests = []

    for source_name, values in (("full_a20_history", history_states), ("blind_oos_a20", blind_states)):
        for block_length in (20, 50, 100, 200):
            result = bootstrap_state_p(values, block_length, SEED_BASE + block_length + (1000 if source_name == "blind_oos_a20" else 0), observed_high)
            tests.append({
                "test_key": f"state_observed_high_count::{source_name}::L{block_length}",
                "endpoint": "state_persistence", "source": source_name, "block_length": block_length,
                "replicates": B, "observed_statistic": observed_high, **result,
            })

    for block_length in CAPTURE_BLOCKS:
        result = bootstrap_capture_p(terminal_capture, observed_capture, block_length, SEED_BASE + 2000 + block_length)
        tests.append({
            "test_key": f"capture_mean_lower_tail::terminal_high_run::L{block_length}",
            "endpoint": "conditional_capture_response", "source": "A20 terminal high-state run",
            "block_length": block_length, "replicates": B, "observed_statistic": observed_capture, **result,
        })
    holm_adjust(tests)

    mse = {}
    for key, pred_key in (
        ("q75_state", "prediction"), ("a19_ols", "a19_ols_prediction"),
        ("prior_mean400", "baseline_mean400"), ("prior_mean20", "baseline_mean20"),
    ):
        predictions = [float(r[pred_key]) for r in ext]
        mse[key] = sum((r["capture"] - p) ** 2 for r, p in zip(ext, predictions)) / len(ext)

    combined_prefix = 0
    for value in extension_states:
        if value != 1:
            break
        combined_prefix += 1
    mse_gain, gain_ci = sum(extension_gains) / len(extension_gains), moving_block_gain_ci(extension_gains)
    state_tests = [t for t in tests if t["endpoint"] == "state_persistence"]
    capture_tests = [t for t in tests if t["endpoint"] == "conditional_capture_response"]

    report = {
        "schema_version": "1.0", "experiment_id": "Q141-A22", "analysis_date": DATE,
        "decision": {
            "state_persistence_shift": "NOT_CONFIRMED_UNDER_DEPENDENCE_PRESERVING_NULL",
            "conditional_capture_response_drop": "SUGGESTIVE_BUT_NOT_CONFIRMED_AFTER_HOLM",
            "q75_predictive_skill": "NOT_CONFIRMED", "production_promotion": False,
        },
        "design": {
            "a20_rows": len(hist), "a21_extension_rows": len(ext),
            "extension_period": [ext[0]["target_date"], ext[-1]["target_date"]],
            "target_window": 20, "stationary_bootstrap_replicates_per_test": B,
            "state_block_lengths": list(STATE_BLOCKS), "capture_block_lengths": list(CAPTURE_BLOCKS),
            "registered_diagnostic_test_family_size": 12,
            "holm_scope": "All 12 A22 state-persistence and conditional-capture block-length diagnostics together; does not correct the entire prior SONAR research history.",
            "hypothesis_status": "Exploratory post-extension audit; A21 outcomes were visible before A22 was formulated.",
        },
        "source_lineage": {
            "a20_path": "reports/sequence_agent/q141_a20_drift_quantile_state_2026-11-14_target_ledger.csv",
            "a20_rows": len(hist), "a20_first_target": hist[0]["target_date"], "a20_last_target": hist[-1]["target_date"],
            "a21_path": "reports/sequence_agent/q141_a21_q7_source_extension_2026-11-14_extension_target_ledger.csv",
            "a21_rows": len(ext), "a21_first_target": ext[0]["target_date"], "a21_last_target": ext[-1]["target_date"],
            "strict_prior_all_rows": True,
        },
        "historical_split_metrics": split_summary(hist),
        "state_diagnostics": {
            "historical_high_rate": sum(history_states) / len(history_states),
            "historical_longest_high_run": longest_run(history_states),
            "historical_state_acf": {str(lag): acf(history_states, lag) for lag in (1, 2, 5, 10, 20, 50, 100, 200)},
            "blind_oos_high_rate": sum(blind_states) / len(blind_states),
            "blind_oos_longest_high_run": longest_run(blind_states),
            "terminal_high_run": {
                "length": len(terminal), "start_date": terminal[0]["target_date"], "end_date": terminal[-1]["target_date"],
                "mean_capture": sum(terminal_capture) / len(terminal_capture), "last_20_mean_capture": previous20_capture,
            },
            "extension_high_count": observed_high, "extension_targets": len(ext),
            "extension_high_rate": observed_high / len(ext),
            "combined_terminal_high_run_length": len(terminal) + combined_prefix,
            "extension_continues_prior_high_run": bool(extension_states and extension_states[0] == 1),
            "state_bootstrap_min_holm_12": min(t["p_holm_12"] for t in state_tests),
        },
        "conditional_capture_response": {
            "terminal_high_run_mean_capture": sum(terminal_capture) / len(terminal_capture),
            "extension_mean_capture": observed_capture,
            "extension_minus_previous20_capture": observed_capture - previous20_capture,
            "extension_minus_terminal_run_capture": observed_capture - sum(terminal_capture) / len(terminal_capture),
            "stationary_bootstrap_min_holm_12": min(t["p_holm_12"] for t in capture_tests),
            "interpretation": "The extension mean is descriptively low relative to the preceding high-state run, but the joint 12-test Holm family does not confirm a response shift.",
        },
        "extension_forecast_errors": {
            "mean_q75_mse_gain_vs_mean400": mse_gain,
            "q75_mse_gain_circular_moving_block5_ci95": gain_ci,
            "positive_per_target_gain_count": sum(1 for x in extension_gains if x > 0),
            "targets": len(extension_gains), "mse": mse,
        },
        "bootstrap_tests": tests,
        "limitations": [
            "A22 is an exploratory audit formulated after the A21 extension responses were visible; its p-values are not confirmatory.",
            "Only 20 appended targets are available.",
            "The state process is highly autocorrelated and nonstationary across Discovery, Validation and Blind OOS.",
            "Stationary bootstrap preserves local temporal dependence of scalar state/capture summaries, not the full 1,023-dimensional formula-rank vector.",
            "The Holm family contains the 12 A22 diagnostics only and does not correct for all prior SONAR hypothesis selection.",
            "Structural capture is a formula-profile fit statistic, not exact-ticket accuracy or a probability of winning.",
        ],
        "next_action": "Keep the 2026-11-14 A21 freeze immutable. After the official result is ingested, append-only evaluate it; continue prospective monitoring without retuning q75 or the 400-target window.",
    }
    return report, tests


def write_outputs(hist, ext, report, bootstrap_rows, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_json = out / f"{PREFIX}_report.json"
    report_md = out / f"{PREFIX}_report.md"
    ledger_path = out / f"{PREFIX}_target_ledger.csv"
    bootstrap_path = out / f"{PREFIX}_bootstrap_summary.csv"
    checkpoint_path = out / f"{PREFIX}_checkpoint.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Q141-A22 — Conditional response-shift audit", "",
        "**Decision:** state persistence shift not confirmed; conditional capture response drop suggestive but not confirmed after Holm; Q75 predictive skill not confirmed.", "",
        "## Observed structure", "",
        f"- A20 historical terminal high-state run: {report['state_diagnostics']['terminal_high_run']['length']} targets, {report['state_diagnostics']['terminal_high_run']['start_date']} to {report['state_diagnostics']['terminal_high_run']['end_date']}.",
        f"- A21 extension: {report['state_diagnostics']['extension_high_count']}/20 high-state targets; combined uninterrupted high run: {report['state_diagnostics']['combined_terminal_high_run_length']}.",
        f"- State ACF(1): {report['state_diagnostics']['historical_state_acf']['1']:.6f}; ACF(20): {report['state_diagnostics']['historical_state_acf']['20']:.6f}.", "",
        "## Conditional capture response", "",
        f"- Previous terminal high-run mean: {report['conditional_capture_response']['terminal_high_run_mean_capture']:.6f}.",
        f"- A21 extension mean: {report['conditional_capture_response']['extension_mean_capture']:.6f}.",
        f"- Difference versus preceding 20 targets: {report['conditional_capture_response']['extension_minus_previous20_capture']:.6f}.",
        f"- Mean Q75 MSE gain versus prior-400 baseline: {report['extension_forecast_errors']['mean_q75_mse_gain_vs_mean400']:.6f}.",
        f"- Circular block-5 bootstrap 95% interval for the 20-target MSE gain: {report['extension_forecast_errors']['q75_mse_gain_circular_moving_block5_ci95']}.", "",
        "## Dependence-preserving null", "",
        "Twelve stationary-bootstrap diagnostics were run (20,000 replicates each): eight state-persistence tests using the full A20 history and Blind OOS subset, plus four lower-tail capture-response tests conditional on the terminal high-state run. Holm correction was applied jointly across all 12 tests.", "",
        "| Test | Block length | Raw p | Holm p |", "|---|---:|---:|---:|",
    ]
    for t in bootstrap_rows:
        lines.append(f"| {t['test_key']} | {t['block_length']} | {t['p_raw']:.6f} | {t['p_holm_12']:.6f} |")
    lines += ["", "## Chronological splits", "", "| Split | Targets | High-state rate | Longest high run | Mean Q75 MSE gain vs mean400 |", "|---|---:|---:|---:|---:|"]
    for split, m in report["historical_split_metrics"].items():
        lines.append(f"| {split} | {m['targets']} | {m['high_rate']:.4f} | {m['longest_high_run']} | {m['mean_q75_mse_gain_vs_mean400']:.6f} |")
    lines += [
        "", "## Interpretation and limits", "",
        "The 20/20 high-state extension is a continuation of the prior terminal high-state run, not a newly observed state transition. The state indicator is strongly autocorrelated. The lower capture response in the extension is descriptively notable, but the joint 12-test Holm family does not confirm a shift. A20/A21 historical Blind OOS is exposed evidence; this analysis was formulated after the A21 extension was visible and is exploratory.",
        "", "The response is structural capture, not candidate-number or exact-quintet accuracy. The stationary bootstrap preserves temporal dependence in scalar summaries but not the complete multivariate formula-rank panel. No engine is promoted and no freeze is changed.", "",
        f"Next action: {report['next_action']}", "",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")

    ledger_rows = []
    for row in hist + ext:
        ledger_rows.append({
            "source": row["source"], "split": row["split"], "target_index": row["target_index"],
            "target_date": row["target_date"], "cutoff_date": row["cutoff_date"],
            "state": "high" if row["state"] else "low", "drift": row["drift"],
            "capture_response": row["capture"], "q75_prediction": row["prediction"],
            "baseline_mean400": row["baseline_mean400"], "mse_gain_vs_mean400": row["gain"],
            "strict_prior": True,
        })
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger_rows)

    with bootstrap_path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["test_key", "endpoint", "source", "block_length", "replicates", "observed_statistic",
                  "null_mean", "null_ci95_lower", "null_ci95_upper", "exceedances", "p_raw", "p_holm_12"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in bootstrap_rows:
            writer.writerow({
                "test_key": row["test_key"], "endpoint": row["endpoint"], "source": row["source"],
                "block_length": row["block_length"], "replicates": row["replicates"],
                "observed_statistic": row["observed_statistic"], "null_mean": row["null_mean"],
                "null_ci95_lower": row["null_ci95"][0], "null_ci95_upper": row["null_ci95"][1],
                "exceedances": row["exceedances"], "p_raw": row["p_raw"], "p_holm_12": row["p_holm_12"],
            })

    checkpoint = {
        "schema_version": "1.0", "experiment_id": "Q141-A22",
        "status": "COMPUTED_PENDING_REMOTE_READBACK",
        "source_rows": {"a20": len(hist), "a21": len(ext)},
        "target_range": [hist[0]["target_date"], ext[-1]["target_date"]],
        "replay_required": True, "promotion_allowed": False,
    }
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return [report_json, report_md, ledger_path, bootstrap_path, checkpoint_path]


def run(a20_path, a21_path, out_dir):
    hist, ext = validate_inputs(read_csv(a20_path), read_csv(a21_path))
    report, bootstrap_rows = analyze(hist, ext)
    return write_outputs(hist, ext, report, bootstrap_rows, out_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a20-ledger", default="reports/sequence_agent/q141_a20_drift_quantile_state_2026-11-14_target_ledger.csv")
    parser.add_argument("--a21-ledger", default="reports/sequence_agent/q141_a21_q7_source_extension_2026-11-14_extension_target_ledger.csv")
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    args = parser.parse_args()
    outputs = run(args.a20_ledger, args.a21_ledger, args.out_dir)
    print("Q141_A22_ANALYSIS_COMPLETE", len(outputs))


if __name__ == "__main__":
    main()
