#!/usr/bin/env python3
"""Freeze the first Q141-A7/B11 prospective prediction without reading its outcome."""
from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(".")
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_a7_fresh59_behaviour as a7

TARGET_DATE = "2026-11-13"
TARGET_TIME_LOCAL = "2026-11-13T20:00:00+01:00"
ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
ATTESTATION_PATH = ROOT / "reports/sequence_agent/q141_a7_b11_official_prior_attestation_2026-11-13.json"
OUT = ROOT / "reports/sequence_agent"
SNAPSHOT = OUT / "q141_a7_b11_prediction_freeze_2026-11-13.json"
LEDGER = OUT / "q141_a7_b11_prospective_ledger_2026-11-13.csv"
REPORT = OUT / "q141_a7_b11_freeze_report_2026-11-13.md"
MANIFEST = OUT / "q141_a7_b11_prospective_manifest_2026-11-13.json"
CHECKPOINT = OUT / "q141_a7_b11_prospective_checkpoint_2026-11-13.json"
SENTINEL = (1, 2, 3, 4, 5)

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def git_blob_sha1(path):
    b = Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode() + b).hexdigest()

def top_numbers(scores, k):
    order = np.lexsort((np.arange(1, 41), -np.round(np.asarray(scores, dtype=float), 12)))
    return (order[:k] + 1).astype(int).tolist()

def main():
    for p in (SNAPSHOT, LEDGER, REPORT, MANIFEST, CHECKPOINT):
        if p.exists():
            raise SystemExit(f"FREEZE_BLOCKED: refusing to overwrite existing append-only file {p}")
    now = datetime.now(timezone.utc)
    target = datetime.fromisoformat(TARGET_TIME_LOCAL).astimezone(timezone.utc)
    if now >= target:
        raise SystemExit("FREEZE_BLOCKED: target draw time has passed; do not create a retrospective freeze")

    att = json.loads(ATTESTATION_PATH.read_text(encoding="utf-8"))
    assert att["status"] == "OFFICIAL_PRIOR_DRAW_CONFIRMED"
    assert att["verified_prior_draw"]["date"] == "2026-11-12"
    assert att["verified_prior_draw"]["contest_number"] == 316
    assert att["verified_prior_draw"]["numbers"] == [2, 4, 7, 23, 33]
    assert att["repository_archive"]["blob_sha1"] == ARCHIVE_BLOB
    assert att["repository_archive"]["last_numbers"] == [2, 4, 7, 23, 33]

    dates, draws = a7.load_archive(ROOT / "data/storico_daily.csv")
    archive_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:data/storico_daily.csv"], text=True
    ).strip()
    if archive_blob != ARCHIVE_BLOB:
        raise SystemExit(f"FREEZE_BLOCKED: archive blob {archive_blob} != pinned {ARCHIVE_BLOB}")
    if len(draws) != 3406 or dates[-1] != "2026-11-12":
        raise SystemExit("FREEZE_BLOCKED: canonical archive count/date mismatch")
    if list(draws[-1]) != att["verified_prior_draw"]["numbers"]:
        raise SystemExit("FREEZE_BLOCKED: final archive draw differs from official attestation")
    if TARGET_DATE in dates:
        raise SystemExit("FREEZE_BLOCKED: target date already exists in source archive")

    # Append a dummy row only to make the existing strict-prior feature builder
    # emit the next target row. The dummy outcome is never read by that row.
    extended = a7.compute_feature_matrix(draws + [SENTINEL])
    if extended.shape != (3357, 40, 59) or extended.dtype != np.float32:
        raise SystemExit(f"FREEZE_BLOCKED: unexpected extended matrix {extended.shape}/{extended.dtype}")
    current = extended[-1].astype(np.float64)
    prior_targets = extended[-6:-1]
    if prior_targets.shape != (5, 40, 59):
        raise SystemExit("FREEZE_BLOCKED: expected exactly five prior target feature rows")

    prior_rank_history = []
    for row in prior_targets:
        family_ranks = []
        for family in a7.FAMILIES:
            family_score = row[:, a7.FAMILY_INDICES[family]].mean(axis=1)
            family_ranks.append(a7.rank_desc(family_score))
        prior_rank_history.append(family_ranks)
    rank_history = np.asarray(prior_rank_history, dtype=np.int16)
    weights, turnover = a7.weights_from_history(rank_history)

    family_scores = np.stack([
        current[:, a7.FAMILY_INDICES[family]].mean(axis=1)
        for family in a7.FAMILIES
    ], axis=0)
    m0_scores = family_scores.mean(axis=0)
    m1_scores = np.sum(family_scores * weights[:, None], axis=0)
    m0_top5, m1_top5 = top_numbers(m0_scores, 5), top_numbers(m1_scores, 5)
    m0_top10, m1_top10 = top_numbers(m0_scores, 10), top_numbers(m1_scores, 10)

    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    att_bytes = ATTESTATION_PATH.read_bytes()
    payload = {
        "schema_version": "1.0",
        "task_id": "Q141-A7-B11-PROSPECTIVE",
        "status": "PREDICTION_FROZEN_AWAITING_OUTCOME",
        "target": {"date": TARGET_DATE, "scheduled_time_local": TARGET_TIME_LOCAL},
        "frozen_at_utc": now.isoformat().replace("+00:00", "Z"),
        "model": {
            "version": "Q141-A7-B11",
            "adaptive_rule": "family weights proportional to 1/(0.10 + mean normalized absolute rank turnover across the previous five target rows)",
            "comparator": "M0 equal arithmetic mean of seven family scores",
            "tie_policy": "scores rounded to 12 decimals; ties by number ascending",
            "family_names": a7.FAMILIES
        },
        "source": {
            "archive_path": "data/storico_daily.csv",
            "archive_blob_sha1": archive_blob,
            "archive_draw_count": len(draws),
            "prior_cutoff_date": dates[-1],
            "prior_draws": len(draws),
            "last_verified_prior_draw": att["verified_prior_draw"],
            "attestation_path": str(ATTESTATION_PATH),
            "attestation_sha256": sha256_bytes(att_bytes),
            "code_commit_sha": code_commit
        },
        "prior_target_rows_for_weights": dates[-5:],
        "family_turnover": {name: float(turnover[i]) for i, name in enumerate(a7.FAMILIES)},
        "family_weights_m1": {name: float(weights[i]) for i, name in enumerate(a7.FAMILIES)},
        "m0_top5": m0_top5,
        "m1_top5": m1_top5,
        "m0_top10": m0_top10,
        "m1_top10": m1_top10,
        "score_vectors": [
            {"number": n, "m0": float(m0_scores[n-1]), "m1": float(m1_scores[n-1])}
            for n in range(1, 41)
        ],
        "integrity": {
            "feature_vector_sha256": sha256_bytes(current.astype("<f4").tobytes(order="C")),
            "prior_rank_history_sha256": sha256_bytes(rank_history.astype("<i2").tobytes(order="C")),
            "no_actual_outcome_in_record": True,
            "score_before_target_outcome": True,
            "no_retuning": True
        }
    }
    payload["prediction_sha256"] = sha256_bytes(canonical_bytes(payload))
    SNAPSHOT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    row = {
        "target_date": TARGET_DATE,
        "target_time_local": TARGET_TIME_LOCAL,
        "prior_cutoff_date": dates[-1],
        "prior_draws": len(draws),
        "archive_blob_sha1": archive_blob,
        "code_commit_sha": code_commit,
        "prediction_sha256": payload["prediction_sha256"],
        "m0_top5": " ".join(map(str, m0_top5)),
        "m1_top5": " ".join(map(str, m1_top5)),
        "m0_top10": " ".join(map(str, m0_top10)),
        "m1_top10": " ".join(map(str, m1_top10)),
        "outcome_status": "PENDING_OFFICIAL_PUBLICATION"
    }
    with LEDGER.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    REPORT.write_text(
        "# Q141-A7 / B11 — first prospective prediction freeze\n\n"
        f"- Target: **{TARGET_DATE}**, scheduled at **20:00 Europe/Rome**.\n"
        f"- Frozen at: {payload['frozen_at_utc']}.\n"
        f"- Prior cutoff: **{dates[-1]}** ({len(draws)} verified prior draws).\n"
        f"- Prior contest 316 (2026-11-12): **2, 4, 7, 23, 33**, reconciled to the official VinciCasa archive attestation.\n"
        f"- M0 Top-5: **{', '.join(map(str, m0_top5))}**.\n"
        f"- M1 Top-5: **{', '.join(map(str, m1_top5))}**.\n"
        f"- Prediction SHA-256: {payload['prediction_sha256']}.\n\n"
        "This is a pre-outcome research freeze, not a validated predictive advantage or a recommendation to play. "
        "No target outcome has been read or appended. No interim efficacy analysis or retuning is permitted. "
        "The first paired efficacy analysis remains deferred until 200 consecutive eligible official draws are frozen and reconciled.\n",
        encoding="utf-8"
    )

    files = [SNAPSHOT, LEDGER, REPORT]
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-A7-B11-PROSPECTIVE",
        "status": "PREDICTION_FROZEN_LOCAL_PENDING_REMOTE_READBACK",
        "target_date": TARGET_DATE,
        "prior_cutoff_date": dates[-1],
        "archive_blob_sha1": archive_blob,
        "code_commit_sha": code_commit,
        "prediction_sha256": payload["prediction_sha256"],
        "outputs": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": sha256_bytes(p.read_bytes()),
                "git_blob_sha1": git_blob_sha1(p)
            } for p in files
        }
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-A7-B11-PROSPECTIVE",
        "status": "PREDICTION_FROZEN_LOCAL_PENDING_REMOTE_READBACK",
        "target_date": TARGET_DATE,
        "prediction_sha256": payload["prediction_sha256"],
        "prediction_path": str(SNAPSHOT),
        "ledger_path": str(LEDGER),
        "manifest_path": str(MANIFEST),
        "prior_cutoff_date": dates[-1],
        "prior_draws": len(draws),
        "prospective_predictions_frozen": 1,
        "prospective_outcomes_reconciled": 0,
        "next_action": "Wait for official publication of the 2026-11-13 outcome; reconcile it without changing the frozen prediction, then continue the append-only 200-draw protocol with no interim efficacy peeking.",
        "governance": {
            "pr6_untouched": True, "pr7_untouched": True, "pr8_untouched": True,
            "pr89_untouched": True, "engine_promotion": False,
            "canonical_archive_mutation": False, "shadow_insertion": False, "merge": False
        }
    }
    CHECKPOINT.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": checkpoint["status"],
        "target_date": TARGET_DATE,
        "prior_cutoff_date": dates[-1],
        "prediction_sha256": payload["prediction_sha256"],
        "m0_top5": m0_top5,
        "m1_top5": m1_top5,
        "family_weights_m1": payload["family_weights_m1"],
        "outputs": {p.name: {"bytes": p.stat().st_size, "sha256": sha256_bytes(p.read_bytes())} for p in [SNAPSHOT, LEDGER, REPORT, MANIFEST, CHECKPOINT]}
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
