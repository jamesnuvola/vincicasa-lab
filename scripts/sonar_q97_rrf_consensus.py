#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, gzip, hashlib, io, json, math
from pathlib import Path
import numpy as np

EXP = "SONAR-Q97-FIVE-MODEL-RRF-CONSENSUS-2026-11-10"
LEDGER_SHA = "be4e24f4a4a90261950583cf5752065bd3b735d8351d3637fba4fadeaed67b04"
ARCHIVE_SHA = "ba0c8f4e78805e72d04a1b731e1882a9edd3ac71a2bc35c92409540d9ebdec61"
ARCHIVE_BLOB = "8d3e19f0b417024ba32e576697eac0648d12ab86"
RUN_ID, ARTIFACT_ID = 42755127353, 13735162512
ARTIFACT_SHA = "a00b1dd2090679f93d604132697994c60bb69bbbd443d25e737597ae3d53cdc0"
MODELS = {
    "BASE_EQUAL42": "base_equal42",
    "Q90_PAIR_INTERACTION": "q90_pair_interaction_transfer",
    "Q93_SPECTRAL_K2": "q93_spectral_k2",
    "Q94_STABILITY": "q94_stability_weighted",
    "Q94_INSTABILITY": "q94_instability_weighted",
}
KS, C, BLOCK, PERMS, BOOTS = (5, 10, 20), 20, 20, 50000, 10000


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def validate_rank(r):
    if len(r) != 40 or sorted(r) != list(range(1, 41)):
        raise ValueError("rank vector is not a permutation of 1..40")


def order_from_rank(r):
    validate_rank(r)
    return sorted(range(1, 41), key=lambda n: (r[n - 1], n))


def rrf_order(vectors, c=C):
    if set(vectors) != set(MODELS):
        raise ValueError("wrong RRF source family")
    for r in vectors.values():
        validate_rank(r)
    scores = [sum(1.0 / (c + vectors[m][n - 1]) for m in MODELS) for n in range(1, 41)]
    return sorted(range(1, 41), key=lambda n: (-scores[n - 1], n))


def holm(p):
    ix = sorted(range(len(p)), key=lambda i: p[i])
    out, run = [0.0] * len(p), 0.0
    for rank, i in enumerate(ix):
        run = max(run, (len(p) - rank) * p[i])
        out[i] = min(1.0, run)
    return out


def exact_null_p(total, n, k):
    den = math.comb(40, 5)
    pmf = np.array([
        math.comb(k, x) * math.comb(40-k, 5-x) / den
        if 0 <= x <= 5 and x <= k and 5-x <= 40-k else 0.0
        for x in range(6)
    ])
    size = 1
    while size < n * 5 + 1:
        size *= 2
    dist = np.fft.irfft(np.fft.rfft(pmf, size) ** n, size)[:n*5+1]
    return float(np.maximum(dist, 0)[total:].sum())


def block_p(d, seed, reps=PERMS, block=BLOCK):
    d = np.asarray(d, dtype=float)
    sums = np.array([d[i:i+block].sum() for i in range(0, len(d), block)])
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(reps, len(sums)))
    p = (1 + int(np.count_nonzero(signs @ sums >= d.sum()))) / (reps + 1)
    return float(p), len(sums), len(d) % block or block


def block_ci(d, seed, reps=BOOTS, block=BLOCK):
    d = np.asarray(d, dtype=float)
    n, nb = len(d), int(math.ceil(len(d) / block))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(reps, nb))
    ix = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    means = d[ix].reshape(reps, -1)[:, :n].mean(axis=1)
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def hits(order, actual, k):
    return sum(n in actual for n in order[:k])


def write_gz(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(input_path, manifest_path, outdir):
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get("status") != "ACCEPTANCE_PASS":
        raise ValueError("Q94 source manifest not accepted")
    if manifest.get("source_archive_git_blob_sha1") != ARCHIVE_BLOB or manifest.get("source_archive_sha256") != ARCHIVE_SHA:
        raise ValueError("source archive fingerprint mismatch")
    input_sha = sha(input_path)
    if input_sha != LEDGER_SHA or input_sha != manifest["files"]["target_ledger"]["sha256"]:
        raise ValueError("Q94 target ledger checksum mismatch")
    if manifest.get("draws") != 3403 or manifest.get("targets") != 3203:
        raise ValueError("unexpected Q94 source dimensions")

    with gzip.open(input_path, "rt", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    split_expected = {"discovery": 1921, "validation": 641, "blind_oos": 641}
    split_counts = {s: sum(r["split"] == s for r in rows) for s in split_expected}
    if len(rows) != 3203 or split_counts != split_expected:
        raise ValueError(f"target/split mismatch: {len(rows)}, {split_counts}")

    source_snapshot, target_ledger = [], []
    orders = {m: [] for m in MODELS}
    orders["Q97_RRF5"] = []
    actuals, splits, union_sizes, outside_counts = [], [], [], []
    prev = None
    for i, row in enumerate(rows):
        target, cutoff = dt.date.fromisoformat(row["target_date"]), dt.date.fromisoformat(row["cutoff_date"])
        if cutoff >= target or (prev is not None and target <= prev):
            raise ValueError(f"cutoff/order error at row {i}")
        prev = target
        if int(row["prior_draws"]) != 200 + i:
            raise ValueError(f"prior count mismatch at row {i}")
        actual_list = [int(x) for x in row["actual_quintet"].split()]
        if len(actual_list) != 5 or actual_list != sorted(set(actual_list)) or any(x < 1 or x > 40 for x in actual_list):
            raise ValueError(f"invalid actual quintet at row {i}")

        vectors, component = {}, {}
        for name, prefix in MODELS.items():
            vectors[name] = [int(row[f"rank_{prefix}_{n:02d}"]) for n in range(1, 41)]
            component[name] = order_from_rank(vectors[name])
            orders[name].append(component[name])
        fused = rrf_order(vectors, C)
        orders["Q97_RRF5"].append(fused)
        actual = set(actual_list)
        actuals.append(actual)
        splits.append(row["split"])
        union = set().union(*(set(v[:20]) for v in component.values()))
        union_sizes.append(len(union))
        outside_counts.append(len(set(fused[:20]) - union))

        snap = {"target_date": row["target_date"], "cutoff_date": row["cutoff_date"],
                "prior_draws": row["prior_draws"], "split": row["split"],
                "actual_quintet": row["actual_quintet"]}
        for name, ranking in component.items():
            snap[f"ranked_{name.lower()}"] = " ".join(map(str, ranking))
        source_snapshot.append(snap)

        led = {"target_date": row["target_date"], "cutoff_date": row["cutoff_date"],
               "prior_draws": row["prior_draws"], "split": row["split"],
               "actual_quintet": row["actual_quintet"], "component_top20_union_size": len(union),
               "rrf_top20_outside_component_union": outside_counts[-1],
               "rrf_top20": " ".join(map(str, fused[:20]))}
        for name, ranking in component.items():
            led[f"{name.lower()}_top20"] = " ".join(map(str, ranking[:20]))
        for name, ranking in orders.items():
            for k in KS:
                led[f"{name.lower()}_top{k}_hits"] = hits(ranking[-1], actual, k)
        target_ledger.append(led)

    metrics = {}
    for split in split_expected:
        ix = [i for i, s in enumerate(splits) if s == split]
        metrics[split] = {"targets": len(ix), "strategies": {}}
        for name, rankings in orders.items():
            em = {}
            for k in KS:
                total = sum(hits(rankings[i], actuals[i], k) for i in ix)
                item = {"hits": int(total), "mean_hits_per_target": total / len(ix),
                        "null_expected_hits_per_target": 5 * k / 40}
                if name in ("BASE_EQUAL42", "Q97_RRF5"):
                    item["exact_hypergeometric_upper_tail_p"] = exact_null_p(total, len(ix), k)
                em[f"top{k}"] = item
            metrics[split]["strategies"][name] = em

    blind = [i for i, s in enumerate(splits) if s == "blind_oos"]
    comparisons = []
    for mi, comp in enumerate(MODELS):
        for k in KS:
            d = np.array([hits(orders["Q97_RRF5"][i], actuals[i], k) -
                          hits(orders[comp][i], actuals[i], k) for i in blind], dtype=float)
            seed = 97000 + mi * 10 + k
            p, blocks, tail = block_p(d, seed)
            ci = block_ci(d, 97100 + mi * 10 + k)
            comparisons.append({
                "comparator": comp, "endpoint": f"top{k}", "n": len(d),
                "mean_difference_hits_per_target": float(d.mean()),
                "mean_difference_total_hits": int(d.sum()),
                "block_signflip": {"block_length": BLOCK, "blocks": blocks, "tail_block_size": tail,
                                   "replicates": PERMS, "seed": seed, "p_raw": p,
                                   "alternative": "RRF has more hits"},
                "circular_block_bootstrap": {"block_length": BLOCK, "replicates": BOOTS,
                                             "seed": 97100 + mi * 10 + k, "ci95": ci}
            })
    adj = holm([x["block_signflip"]["p_raw"] for x in comparisons])
    for x, p in zip(comparisons, adj):
        x["block_signflip"]["p_holm_global_15"] = p

    primary = next(x for x in comparisons if x["comparator"] == "BASE_EQUAL42" and x["endpoint"] == "top20")
    ci = primary["circular_block_bootstrap"]["ci95"]
    mean = primary["mean_difference_hits_per_target"]
    p_holm = primary["block_signflip"]["p_holm_global_15"]
    gate = "MET" if mean > 0 and ci[0] > 0 and p_holm < 0.05 else "NOT_MET"

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    snap_path = outdir / "q97_rrf_consensus_source_snapshot_2026-11-10.csv.gz"
    ledger_path = outdir / "q97_rrf_consensus_target_ledger_2026-11-10.csv.gz"
    report_path = outdir / "q97_rrf_consensus_report_2026-11-10.json"
    checkpoint_path = outdir / "q97_rrf_consensus_checkpoint_2026-11-10.md"
    validation_path = outdir / "q97_rrf_consensus_validation_2026-11-10.json"
    write_gz(snap_path, source_snapshot)
    write_gz(ledger_path, target_ledger)

    report = {
        "schema_version": "1.0", "experiment_id": EXP,
        "status": "POST_HOC_EXPLORATORY_COMPLETE",
        "validation_status": "NO_INCREMENTAL_LIFT_DEMONSTRATED",
        "registration_status": "POST_HOC_FIXED_FORMULA; COMPONENT_FAMILIES_WERE_PREVIOUSLY_EXPOSED",
        "source": {"q94_workflow_run_id": RUN_ID, "q94_artifact_id": ARTIFACT_ID,
                   "q94_artifact_sha256": ARTIFACT_SHA, "q94_target_ledger_sha256": input_sha,
                   "source_archive_git_blob_sha1": ARCHIVE_BLOB, "source_archive_sha256": ARCHIVE_SHA,
                   "draw_count": 3403, "target_count": len(rows),
                   "first_target": rows[0]["target_date"], "last_target": rows[-1]["target_date"]},
        "hypothesis": "Equal-weight RRF of five prior-only rankings improves Top-20 mean hits over Equal42 and is not materially inferior to its components.",
        "formula": {"score": "S(n)=sum_m 1/(20+r_m(n))", "c": C,
                    "weights": {m: 1.0 for m in MODELS},
                    "tie_break": "descending score, then ascending number",
                    "candidate_domain": "1..40", "tuning": "none"},
        "split_results": metrics,
        "blind_oos_inference": {"n": len(blind),
            "primary_gate": {"mean_difference_hits_per_target": mean,
                             "mean_difference_total_hits": primary["mean_difference_total_hits"],
                             "ci95": ci, "p_raw": primary["block_signflip"]["p_raw"],
                             "p_holm_global_15": p_holm, "status": gate},
            "family_size": 15, "comparisons": comparisons},
        "consensus_diagnostics": {"component_top20_union_size_mean": float(np.mean(union_sizes)),
                                  "component_top20_union_size_min": min(union_sizes),
                                  "component_top20_union_size_max": max(union_sizes),
                                  "rrf_top20_outside_component_union_total": sum(outside_counts),
                                  "rrf_top20_outside_union_targets": sum(x > 0 for x in outside_counts)},
        "integrity": {"strict_prior_cutoffs": len(rows), "all_cutoffs_precede_targets": True,
                      "prior_draws_start_at_200_and_increment_by_one": True,
                      "all_rank_vectors_valid_permutations": True, "all_actual_quintets_valid": True,
                      "actuals_used_only_after_rankings_built": True, "missing_forecasts": 0},
        "statistical_controls": {"exact_null": "Hypergeometric(40,k,5), convolved over each split",
                                 "paired_test": "one-sided block sign-flip, block length 20, 50,000 reps",
                                 "bootstrap": "circular moving-block bootstrap, block length 20, 10,000 reps",
                                 "multiple_testing": "Holm across 5 comparators x 3 endpoints"},
        "limitations": [
            "Post-hoc exploratory ensemble; component families were previously examined.",
            "Historical Blind OOS is prior-exposed and is not a virgin prospective holdout.",
            "Block sign-flip assumes exchangeability of contiguous 20-target block signs under the null.",
            "RRF is a ranking aggregation, not a physical or causal mechanism.",
            "No historical result establishes an advantage for future random draws."
        ],
        "decision_policy": {"promotion_allowed": False, "production_change_allowed": False,
                            "merge_allowed": False, "human_review_required": True,
                            "prospective_confirmation_required": True},
        "next_action": "Stop retrospective RRF tuning; continue Q60 append-only prospective collection until at least 200 complete paired targets.",
        "reproducibility": {"script_sha256": sha(Path(__file__).resolve()),
                            "source_snapshot_sha256": sha(snap_path), "target_ledger_sha256": sha(ledger_path)}
    }
    write_json(report_path, report)
    checkpoint = (
        "# SONAR Q97 — five-model RRF consensus checkpoint (2026-11-10)\n\n"
        f"- Status: POST_HOC_EXPLORATORY_COMPLETE; gate {gate}.\n"
        f"- Source Q94 run {RUN_ID}, artifact {ARTIFACT_ID}; ledger SHA-256 {input_sha}.\n"
        "- Archive: 3,403 draws through 2026-11-09; 3,203 strict-prior targets.\n"
        "- Splits: Discovery 1,921; Validation 641; historical Blind OOS 641.\n"
        "- Formula: sum of 1/(20+rank) across five fixed rankings; ties by ascending number.\n"
        f"- Blind Top-20 difference vs Equal42: {mean:+.9f} hits/target; 95% CI [{ci[0]:+.9f}, {ci[1]:+.9f}].\n"
        f"- Block sign-flip raw p {primary['block_signflip']['p_raw']:.6f}; global Holm p {p_holm:.6f}.\n"
        "- 15 paired tests, 50,000 sign flips, 10,000 circular block bootstraps, block length 20.\n"
        "- All prior cutoffs and 16,015 source rank vectors checked; source snapshot and target ledger persisted.\n\n"
        "Post-hoc exploratory only: component families were previously examined and historical Blind OOS is not virgin. "
        "No promotion, production change, freeze change or merge. Stop retrospective tuning; continue Q60 prospective collection.\n"
    )
    checkpoint_path.write_text(checkpoint, encoding="utf-8")
    validation = {
        "experiment_id": EXP, "status": "PASS", "source_ledger_sha256": input_sha,
        "target_count": len(rows), "split_counts": split_counts,
        "strict_prior_cutoffs": len(rows), "rank_vector_checks": len(rows) * len(MODELS),
        "paired_test_count": len(comparisons), "holm_family_size": len(comparisons),
        "outputs": {"source_snapshot_sha256": sha(snap_path), "target_ledger_sha256": sha(ledger_path),
                    "report_sha256": sha(report_path), "checkpoint_sha256": sha(checkpoint_path)},
        "decision": gate, "human_review_required": True
    }
    write_json(validation_path, validation)
    return report, validation


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output-dir", type=Path, default=Path("reports/sequence_agent"))
    a = p.parse_args()
    report, validation = run(a.input, a.manifest, a.output_dir)
    print(json.dumps({"status": validation["status"], "decision": validation["decision"],
                      "outputs": validation["outputs"],
                      "primary_gate": report["blind_oos_inference"]["primary_gate"]},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
