#!/usr/bin/env python3
"""Fail-closed validation of the persisted Q90 compressed artifact bundle."""
from __future__ import annotations
import csv, gzip, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
BUNDLE = OUT / "q90_persisted_bundle_manifest.json"
Q90_MANIFEST = OUT / "q90_formula_metrics_manifest.json"
Q90_CHECKPOINT = OUT / "q90_checkpoint_2026-11-04.json"

EXPECTED_DATA_FILES = {
    "adaptive_novelty_checkpoint_2026-11-01.json",
    "adaptive_novelty_checkpoint_2026-11-02.json",
    "adaptive_novelty_checkpoint_2026-11-04.json",
    "adaptive_novelty_feature_catalog.json",
    "adaptive_novelty_feature_matrix.npz",
    "adaptive_novelty_formula_metrics_manifest.json",
    "adaptive_novelty_regime_drift.json",
    "adaptive_novelty_rule_anticipation_metrics.csv.gz",
    "adaptive_novelty_split_metrics.csv.gz",
    "adaptive_novelty_target_ledger.csv.gz",
    "q90_feature_selection.json",
    "q90_formula_catalog.csv.gz",
    "q90_formula_family_split_summary.json",
    "q90_split_metrics.csv.gz",
    "q90_target_ledger.csv.gz",
}
EXPECTED_ROWS = {
    "adaptive_novelty_rule_anticipation_metrics.csv.gz": 59,
    "adaptive_novelty_split_metrics.csv.gz": 177,
    "adaptive_novelty_target_ledger.csv.gz": 197532,
    "q90_formula_catalog.csv.gz": 330429,
    "q90_split_metrics.csv.gz": 991287,
    "q90_target_ledger.csv.gz": 3348,
}

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def hash_uncompressed(path: Path, storage_format: str):
    digest = hashlib.sha256()
    total = 0
    if storage_format == "gzip":
        stream = gzip.open(path, "rb")
    elif storage_format == "raw":
        stream = path.open("rb")
    else:
        raise AssertionError(f"unsupported storage_format={storage_format}")
    with stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total

def csv_rows(path: Path, storage_format: str) -> int:
    if storage_format == "gzip":
        stream = gzip.open(path, "rt", newline="", encoding="utf-8-sig")
    elif storage_format == "raw":
        stream = path.open("rt", newline="", encoding="utf-8-sig")
    else:
        raise AssertionError(f"unsupported CSV storage_format={storage_format}")
    with stream:
        reader = csv.reader(stream)
        rows = sum(1 for _ in reader)
    return max(0, rows - 1)

def main():
    errors = []
    bundle = load_json(BUNDLE)
    q90 = load_json(Q90_MANIFEST)
    checkpoint = load_json(Q90_CHECKPOINT)
    archive_bytes = ARCHIVE.read_bytes()
    archive_blob = git_blob_sha(archive_bytes)
    if bundle.get("task_id") != "Q90": errors.append("bundle task_id mismatch")
    source_artifact = bundle.get("source_artifact", {})
    if source_artifact.get("workflow_run_id") != 42074828349 or source_artifact.get("artifact_id") != 13438797151: errors.append("source artifact identity mismatch")
    if source_artifact.get("artifact_sha256") != "dffd2488a1b33480111442d418c0d8c2f2bcc6a19c31cd938b6480a7b6e9f3b6" or source_artifact.get("artifact_retention_days") != 90: errors.append("source artifact digest/retention mismatch")
    if source_artifact.get("evaluated_head_sha") != "4b41180e4f8f22b554618593559c255055d10f61": errors.append("source artifact evaluated head mismatch")
    if bundle.get("status") not in ("EXACT_BYTE_READBACK_VERIFIED_PENDING_MAIN_CI_HUMAN_REVIEW", "VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION"):
        errors.append("bundle status is not readback-verified/pending review")
    readback = bundle.get("readback_verification", {})
    if readback.get("status") != "VERIFIED_GIT_DATA_API_EXACT_BYTES" or readback.get("data_files_exact_sha_and_bytes_verified") is not True: errors.append("bundle exact-byte readback marker missing")
    if readback.get("data_file_count") != 15 or readback.get("verified_file_count") != 19: errors.append("bundle readback file counts mismatch")
    if bundle.get("archive", {}).get("blob_sha") != archive_blob: errors.append("bundle archive Git blob SHA mismatch")
    if q90.get("archive", {}).get("blob_sha") != archive_blob: errors.append("Q90 manifest archive Git blob SHA mismatch")
    if checkpoint.get("archive_blob_sha") != archive_blob: errors.append("Q90 checkpoint archive Git blob SHA mismatch")
    if bundle.get("archive", {}).get("draw_count") != q90.get("archive", {}).get("draw_count"): errors.append("bundle/Q90 archive draw count mismatch")
    if bundle.get("archive", {}).get("last_date") != q90.get("archive", {}).get("last_date"): errors.append("bundle/Q90 archive cutoff mismatch")
    if q90.get("archive", {}).get("draw_count") != 3398 or q90.get("archive", {}).get("first_date") != "2017-07-17" or q90.get("archive", {}).get("last_date") != "2026-11-04": errors.append("Q90 canonical archive dimensions/cutoff mismatch")
    if q90.get("task_id") != "Q90" or q90.get("formula_grammar", {}).get("formula_count") != 330429: errors.append("Q90 formula catalog dimensions mismatch")
    if q90.get("formula_grammar", {}).get("formula_count_check") != 330429 or q90.get("metrics_rows") != 991287 or q90.get("target_ledger_rows") != 3348: errors.append("Q90 output dimensions mismatch")
    if q90.get("selected_feature_count") != 20 or len(q90.get("selected_features", [])) != 20: errors.append("Q90 selected-feature dimensions mismatch")
    if q90.get("acceptance", {}).get("validator") != "Q90_FORMULA_ACCEPTANCE_PASS": errors.append("Q90 acceptance validator marker missing")
    if q90.get("acceptance", {}).get("artifact_readback") != "VERIFIED_GIT_DATA_API_EXACT_BYTES": errors.append("Q90 artifact readback marker missing")
    if q90.get("acceptance", {}).get("human_review") != "PENDING": errors.append("Q90 human-review gate missing")
    if q90.get("acceptance", {}).get("main_ci") != "PENDING": errors.append("Q90 exact-head CI gate missing")
    persisted_storage = q90.get("persisted_storage", {})
    if persisted_storage.get("format") != "gzip-compressed CSV; raw JSON/NPZ" or persisted_storage.get("bundle_manifest_path") != "reports/sequence_agent/q90_persisted_bundle_manifest.json": errors.append("Q90 persisted storage schema mismatch")
    if checkpoint.get("task_id") != "Q90" or checkpoint.get("formula_count") != 330429 or checkpoint.get("scored_targets") != 3348: errors.append("Q90 checkpoint dimensions mismatch")
    if checkpoint.get("acceptance", {}).get("artifact_readback") != "VERIFIED_GIT_DATA_API_EXACT_BYTES": errors.append("Q90 checkpoint readback marker missing")
    if checkpoint.get("acceptance", {}).get("human_review") != "PENDING": errors.append("Q90 checkpoint human-review gate missing")
    if checkpoint.get("acceptance", {}).get("main_ci") != "PENDING": errors.append("Q90 checkpoint exact-head CI gate missing")
    if checkpoint.get("manifest_sha256") != sha256_bytes(Q90_MANIFEST.read_bytes()): errors.append("Q90 checkpoint manifest SHA mismatch")
    bundle_sha = sha256_bytes(BUNDLE.read_bytes())
    if q90.get("persisted_storage", {}).get("bundle_manifest_sha256") != bundle_sha: errors.append("Q90 manifest bundle-manifest SHA mismatch")
    if checkpoint.get("bundle_manifest_sha256") != bundle_sha: errors.append("Q90 checkpoint bundle-manifest SHA mismatch")
    data_commit = bundle.get("data_commit_sha")
    if not isinstance(data_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", data_commit): errors.append("bundle data_commit_sha missing/invalid")
    if q90.get("persisted_storage", {}).get("data_commit_sha") != data_commit: errors.append("Q90 manifest data commit SHA mismatch")
    entries = bundle.get("data_files", [])
    if persisted_storage.get("data_file_count") != len(entries): errors.append("Q90 manifest data file count mismatch")
    if persisted_storage.get("total_persisted_bytes") != sum(int(x.get("persisted_bytes", 0)) for x in entries): errors.append("Q90 manifest persisted byte total mismatch")
    paths = [x.get("persisted_path") for x in entries]
    if len(paths) != len(set(paths)): errors.append("duplicate persisted paths in bundle manifest")
    expected_paths = {"reports/sequence_agent/" + name for name in EXPECTED_DATA_FILES}
    if set(paths) != expected_paths: errors.append("bundle data file set mismatch")
    entry_by_name = {Path(x.get("persisted_path", "")).name: x for x in entries}
    for item in entries:
        rel = item.get("persisted_path", "")
        path = ROOT / rel
        if not path.is_file():
            errors.append("persisted file missing: " + rel)
            continue
        raw = path.read_bytes()
        if len(raw) != item.get("persisted_bytes"): errors.append("persisted byte count mismatch: " + rel)
        if sha256_bytes(raw) != item.get("persisted_sha256"): errors.append("persisted SHA-256 mismatch: " + rel)
        storage = item.get("storage_format")
        try:
            unc_sha, unc_bytes = hash_uncompressed(path, storage)
        except Exception as exc:
            errors.append("cannot decompress/read persisted file " + rel + ": " + str(exc))
            continue
        if unc_bytes != item.get("uncompressed_bytes"): errors.append("uncompressed byte count mismatch: " + rel)
        if unc_sha != item.get("uncompressed_sha256"): errors.append("uncompressed SHA-256 mismatch: " + rel)
        expected_rows = item.get("uncompressed_rows")
        if expected_rows is not None:
            try:
                actual_rows = csv_rows(path, storage)
                if actual_rows != expected_rows: errors.append(f"CSV row count mismatch: {rel} {actual_rows}!={expected_rows}")
            except Exception as exc:
                errors.append("cannot count CSV rows " + rel + ": " + str(exc))
    for field, filename in (("formula_catalog_sha256", "q90_formula_catalog.csv.gz"),
                             ("split_metrics_sha256", "q90_split_metrics.csv.gz"),
                             ("target_ledger_sha256", "q90_target_ledger.csv.gz"),
                             ("feature_selection_sha256", "q90_feature_selection.json"),
                             ("family_summary_sha256", "q90_formula_family_split_summary.json")):
        item = entry_by_name.get(filename)
        if not item or q90.get(field) != item.get("uncompressed_sha256"): errors.append("Q90 source checksum mismatch: " + field)
    q89 = load_json(OUT / "adaptive_novelty_formula_metrics_manifest.json")
    if q89.get("archive_blob_sha") != archive_blob or q89.get("archive_draw_count") != 3398 or q89.get("scored_targets") != 3348: errors.append("Q89 archive/target dimensions mismatch")
    if q89.get("feature_count") != 59 or q89.get("metrics_rows") != 59 or q89.get("target_ledger_rows") != 197532 or q89.get("split_metrics_rows") != 177: errors.append("Q89 output dimensions mismatch")
    for field, filename in (("ledger_sha256", "adaptive_novelty_target_ledger.csv.gz"),
                            ("split_metrics_sha256", "adaptive_novelty_split_metrics.csv.gz"),
                            ("feature_matrix_sha256", "adaptive_novelty_feature_matrix.npz"),
                            ("regime_drift_sha256", "adaptive_novelty_regime_drift.json")):
        item = entry_by_name.get(filename)
        if not item or q89.get(field) != item.get("uncompressed_sha256"): errors.append("Q89 source checksum mismatch: " + field)
    q89_matrix = q90.get("q89_feature_matrix", {})
    if q89_matrix.get("sha256") != q89.get("feature_matrix_sha256"): errors.append("Q90/Q89 feature matrix checksum mismatch")
    q89_catalog = load_json(OUT / "adaptive_novelty_feature_catalog.json")
    if q89_catalog.get("archive", {}).get("blob_sha") != archive_blob: errors.append("Q89 feature catalog archive SHA mismatch")
    family = load_json(OUT / "q90_formula_family_split_summary.json")
    if family.get("task_id") != "Q90" or family.get("formula_count") != 330429 or len(family.get("family_split_summary", [])) != 21: errors.append("Q90 family/split summary dimensions mismatch")
    if errors:
        for error in errors[:100]: print("Q90_PERSISTED_BUNDLE_INVALID: " + error)
        raise SystemExit(1)
    print(json.dumps({"status":"Q90_PERSISTED_BUNDLE_VALIDATION_PASS","task_id":"Q90","data_file_count":len(entries),
        "data_commit_sha":data_commit,"archive_blob_sha":archive_blob,"archive_draw_count":bundle["archive"]["draw_count"],
        "archive_last_date":bundle["archive"]["last_date"],"formula_count":330429,"metrics_rows":991287,"target_ledger_rows":3348,
        "exact_compressed_and_uncompressed_sha_verified":True,"human_review":"PENDING"},separators=(",",":")))

if __name__ == "__main__": main()
