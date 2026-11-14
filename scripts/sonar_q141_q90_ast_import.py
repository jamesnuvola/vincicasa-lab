#!/usr/bin/env python3
"""Q141-A3: deterministic import of Q90 formulas into typed canonical AST shards."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

ARTIFACT_ID = 13627507532
WORKFLOW_RUN_ID = 42504717670
EXPECTED_ZIP_SHA256 = "12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"
EXPECTED_Q90_ARCHIVE_BLOB = "5d2efd70684e918b27d8f06386d545647898336d"
EXPECTED_Q90_ARCHIVE_DRAWS = 3401
EXPECTED_Q90_ARCHIVE_CUTOFF = "2026-11-07"
EXPECTED_Q90_CATALOG_SHA256 = "a61f77ede7136d4eb88a57932488590741fd0b84ace8307d5dd90c192d520586"
EXPECTED_Q90_MATRIX_SHA256 = "681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49"
EXPECTED_Q90_SELECTION_SHA256 = "0e752f901f1d5f8f7c4b7d8436f38e3939ee2ab7018dc4229a0e1fddd3c08ed9"
EXPECTED_FORMULA_COUNTS = {
    "linear_mean": 262599,
    "pairwise_interaction": 29070,
    "conditional_gate": 38760,
}
EXPECTED_FORMULA_TOTAL = 330429
SHARD_ROWS = 50000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def git_blob_sha1_file(path: Path) -> str:
    data = path.read_bytes()
    return git_blob_sha1(data)


def rational(value: str) -> dict:
    numerator, denominator = Decimal(value).as_integer_ratio()
    return {"numerator": int(numerator), "denominator": int(denominator)}


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ast_identifier(ast: dict) -> str:
    return "Q90AST1-" + sha256_bytes(canonical_json(ast))


def verify_artifact(zip_path: Path, readback_path: Path):
    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    external = readback["external_artifact"]
    source = readback["source"]
    if external["zip_sha256"] != EXPECTED_ZIP_SHA256:
        raise RuntimeError("Q141_A3_BLOCKED: persisted readback manifest artifact digest mismatch")
    if external["member_count"] != 17 or source["artifact_id"] != ARTIFACT_ID:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 artifact identity mismatch")
    if source["artifact_workflow_run_id"] != WORKFLOW_RUN_ID:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 workflow run mismatch")
    if source["q90_archive_git_blob_sha1"] != EXPECTED_Q90_ARCHIVE_BLOB:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 source archive lineage mismatch")
    if source["q90_archive_draws"] != EXPECTED_Q90_ARCHIVE_DRAWS or source["q90_archive_cutoff"] != EXPECTED_Q90_ARCHIVE_CUTOFF:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 archive date boundary mismatch")
    actual_zip_sha = sha256_file(zip_path)
    if actual_zip_sha != external["zip_sha256"]:
        raise RuntimeError(f"Q141_A3_BLOCKED: ZIP SHA-256 mismatch {actual_zip_sha}")
    expected_members = {item["path"]: item for item in external["members"]}
    with zipfile.ZipFile(zip_path, "r") as archive:
        actual_members = {name for name in archive.namelist() if not name.endswith("/")}
        if actual_members != set(expected_members):
            raise RuntimeError("Q141_A3_BLOCKED: ZIP member set mismatch")
        if archive.testzip() is not None:
            raise RuntimeError("Q141_A3_BLOCKED: ZIP CRC validation failed")
        verified = []
        for name, expected in sorted(expected_members.items()):
            digest = hashlib.sha256()
            byte_count = 0
            with archive.open(name, "r") as member:
                for chunk in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(chunk)
                    byte_count += len(chunk)
            actual_sha = digest.hexdigest()
            if byte_count != expected["bytes"] or actual_sha != expected["sha256"]:
                raise RuntimeError(f"Q141_A3_BLOCKED: member integrity mismatch for {name}")
            verified.append({"path": name, "bytes": byte_count, "sha256": actual_sha})
    return readback, verified


def load_json_member(archive: zipfile.ZipFile, name: str) -> dict:
    with archive.open(name, "r") as handle:
        return json.load(handle)


def q90_formula_count(manifest: dict) -> int:
    return int(manifest["formula_grammar"]["formula_count"])


def feature_context(archive: zipfile.ZipFile):
    catalog = load_json_member(archive, "adaptive_novelty_feature_catalog.json")
    selection = load_json_member(archive, "q90_feature_selection.json")
    q90_manifest = load_json_member(archive, "q90_formula_metrics_manifest.json")
    names = list(catalog["baseline_features"]) + list(catalog["new_features"])
    if len(names) != 59 or len(set(names)) != 59:
        raise RuntimeError("Q141_A3_BLOCKED: Q89 feature catalog is not 59 unique names")
    if catalog["feature_count"] != 59:
        raise RuntimeError("Q141_A3_BLOCKED: Q89 feature count mismatch")
    selected = selection["selected_features"]
    if selection["selection_split"] != "discovery" or len(selected) != 20:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 feature selection lineage mismatch")
    family_by_name = {item["feature"]: item["family"] for item in selected}
    selected_names = {item["feature"] for item in selected}
    if not selected_names.issubset(set(names)) or len(family_by_name) != 20:
        raise RuntimeError("Q141_A3_BLOCKED: selected feature references are invalid")
    if q90_manifest["archive"]["blob_sha"] != EXPECTED_Q90_ARCHIVE_BLOB:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 formula manifest archive mismatch")
    if q90_formula_count(q90_manifest) != EXPECTED_FORMULA_TOTAL:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 formula manifest count mismatch")
    if q90_manifest["formula_grammar"]["formula_type_counts"] != EXPECTED_FORMULA_COUNTS:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 formula type-count manifest mismatch")
    if q90_manifest["q89_feature_matrix"]["shape"] != [3351, 40, 59]:
        raise RuntimeError("Q141_A3_BLOCKED: Q89 feature matrix shape mismatch")
    if q90_manifest["q89_feature_matrix"]["dtype"] != "float32":
        raise RuntimeError("Q141_A3_BLOCKED: Q89 feature matrix dtype mismatch")
    if q90_manifest["q89_feature_matrix"]["sha256"] != EXPECTED_Q90_MATRIX_SHA256:
        raise RuntimeError("Q141_A3_BLOCKED: Q89 feature matrix SHA-256 mismatch")
    if q90_manifest["formula_catalog_sha256"] != EXPECTED_Q90_CATALOG_SHA256:
        raise RuntimeError("Q141_A3_BLOCKED: Q90 formula catalog SHA-256 mismatch")
    if selection.get("selection_split") != "discovery":
        raise RuntimeError("Q141_A3_BLOCKED: feature selection was not Discovery-only")
    return names, family_by_name, selected_names, selection, catalog, q90_manifest


def feature_ref(index: int, names: list[str], family_by_name: dict[str, str]) -> dict:
    name = names[index]
    family = family_by_name.get(name)
    if family is None:
        raise ValueError(f"Q90 AST feature is outside the selected 20-feature universe: {name}")
    return {
        "op": "feature_ref",
        "namespace": "Q89",
        "index": int(index),
        "name": name,
        "family": family,
    }


def mean_node(indices: list[int], names: list[str], family_by_name: dict[str, str]) -> dict:
    return {
        "op": "mean",
        "terms": [feature_ref(index, names, family_by_name) for index in sorted(indices)],
        "denominator": len(indices),
        "feature_normalization": "per_target_zscore_across_40_candidates",
    }


def build_ast(row: dict, names: list[str], family_by_name: dict[str, str]) -> tuple[dict, str]:
    formula_type = row["formula_type"]
    indices = [int(value) for value in row["feature_indices"].split(";") if value != ""]
    formula_size = int(row["formula_size"])
    row_names = row["features"].split("+")
    if len(indices) != formula_size or len(set(indices)) != formula_size:
        raise ValueError(f"Invalid source feature indices for {row['formula_id']}")
    if any(index < 0 or index >= len(names) for index in indices):
        raise ValueError(f"Out-of-range Q89 feature index for {row['formula_id']}")
    if [names[index] for index in indices] != row_names:
        raise ValueError(f"Source feature index/name mismatch for {row['formula_id']}")
    if any(names[index] not in family_by_name for index in indices):
        raise ValueError(f"Unselected feature in Q90 formula {row['formula_id']}")

    base = mean_node(indices, names, family_by_name)
    if formula_type == "linear_mean":
        if formula_size not in (4, 5, 6, 7, 8):
            raise ValueError(f"Invalid linear formula size for {row['formula_id']}")
        if any(row[key] for key in ("interaction_pair", "gate_feature", "gate_threshold", "weight")):
            raise ValueError(f"Unexpected parameters on linear formula {row['formula_id']}")
        ast = {"op": "per_number_score", "term": base}

    elif formula_type == "pairwise_interaction":
        if formula_size != 4 or row["gate_feature"] or row["gate_threshold"]:
            raise ValueError(f"Invalid interaction formula fields for {row['formula_id']}")
        pair_names = row["interaction_pair"].split("*")
        if len(pair_names) != 2 or len(set(pair_names)) != 2:
            raise ValueError(f"Invalid interaction pair for {row['formula_id']}")
        index_by_name = {name: index for index, name in enumerate(names)}
        pair_indices = sorted(index_by_name[name] for name in pair_names)
        if not set(pair_indices).issubset(set(indices)):
            raise ValueError(f"Interaction pair is not a subset of the base features for {row['formula_id']}")
        if rational(row["weight"]) != {"numerator": 1, "denominator": 4}:
            raise ValueError(f"Unexpected interaction coefficient for {row['formula_id']}")
        product = {
            "op": "product",
            "factors": [feature_ref(index, names, family_by_name) for index in pair_indices],
        }
        interaction = {
            "op": "scale",
            "coefficient": {"numerator": 1, "denominator": 4},
            "term": {"op": "candidate_zscore", "term": product},
        }
        ast = {"op": "per_number_score", "term": {"op": "add", "terms": [base, interaction]}}

    elif formula_type == "conditional_gate":
        if formula_size != 4 or row["interaction_pair"]:
            raise ValueError(f"Invalid gate formula fields for {row['formula_id']}")
        if row["gate_feature"] not in row_names:
            raise ValueError(f"Gate feature is not part of base formula for {row['formula_id']}")
        gate_index = names.index(row["gate_feature"])
        if rational(row["weight"]) != {"numerator": 1, "denominator": 4}:
            raise ValueError(f"Unexpected gate bonus for {row['formula_id']}")
        threshold = rational(row["gate_threshold"])
        if threshold not in (
            {"numerator": 1, "denominator": 2},
            {"numerator": 1, "denominator": 1},
        ):
            raise ValueError(f"Unexpected gate threshold for {row['formula_id']}")
        gate = {
            "op": "indicator",
            "condition": {
                "op": "greater_equal",
                "left": feature_ref(gate_index, names, family_by_name),
                "right": threshold,
            },
        }
        bonus = {
            "op": "scale",
            "coefficient": {"numerator": 1, "denominator": 4},
            "term": gate,
        }
        ast = {"op": "per_number_score", "term": {"op": "add", "terms": [base, bonus]}}

    else:
        raise ValueError(f"Unknown Q90 formula type: {formula_type}")

    return ast, ast_identifier(ast)


class ShardWriter:
    def __init__(self, output_dir: Path, shard_rows: int = SHARD_ROWS):
        self.output_dir = output_dir
        self.shard_rows = shard_rows
        self.shards = []
        self.index = -1
        self.rows_in_shard = 0
        self.raw_handle = None
        self.gz_handle = None
        self._open_next()

    def _open_next(self):
        self._close_current()
        self.index += 1
        self.rows_in_shard = 0
        self.path = self.output_dir / f"q90_typed_ast_catalog_part_{self.index:02d}.jsonl.gz"
        self.raw_handle = self.path.open("wb")
        self.gz_handle = gzip.GzipFile(
            filename="", mode="wb", fileobj=self.raw_handle, compresslevel=9, mtime=0
        )

    def write(self, record: dict):
        if self.gz_handle is None:
            self._open_next()
        payload = (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        self.gz_handle.write(payload)
        self.rows_in_shard += 1
        if self.rows_in_shard >= self.shard_rows:
            self._close_current()

    def _close_current(self):
        if self.gz_handle is None:
            return
        self.gz_handle.close()
        self.raw_handle.close()
        data = self.path.read_bytes()
        self.shards.append({
            "path": str(self.path.name),
            "rows": self.rows_in_shard,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "git_blob_sha1": git_blob_sha1(data),
        })
        self.gz_handle = None
        self.raw_handle = None

    def close(self):
        self._close_current()


def verify_shards(shards: list[dict], output_dir: Path, expected_rows: int):
    total = 0
    ast_ids = set()
    formula_ids = set()
    type_counts = Counter()
    for shard in shards:
        path = output_dir / shard["path"]
        data = path.read_bytes()
        if len(data) != shard["bytes"] or sha256_bytes(data) != shard["sha256"]:
            raise RuntimeError(f"Q141_A3_BLOCKED: local shard byte/hash mismatch {path.name}")
        if git_blob_sha1(data) != shard["git_blob_sha1"]:
            raise RuntimeError(f"Q141_A3_BLOCKED: local shard Git blob mismatch {path.name}")
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            count = 0
            for line in handle:
                record = json.loads(line)
                ast_id = ast_identifier(record["ast"])
                if ast_id != record["ast_id"]:
                    raise RuntimeError(f"Q141_A3_BLOCKED: AST id mismatch in {path.name}")
                if ast_id in ast_ids or record["source_formula_id"] in formula_ids:
                    raise RuntimeError("Q141_A3_BLOCKED: duplicate AST or source formula ID on shard readback")
                ast_ids.add(ast_id)
                formula_ids.add(record["source_formula_id"])
                type_counts[record["formula_type"]] += 1
                count += 1
                total += 1
            if count != shard["rows"]:
                raise RuntimeError(f"Q141_A3_BLOCKED: shard row count mismatch {path.name}")
    if total != expected_rows or len(ast_ids) != expected_rows or len(formula_ids) != expected_rows:
        raise RuntimeError("Q141_A3_BLOCKED: total AST readback count or uniqueness mismatch")
    if dict(type_counts) != EXPECTED_FORMULA_COUNTS:
        raise RuntimeError("Q141_A3_BLOCKED: AST readback type counts mismatch")
    return {"rows": total, "unique_ast_ids": len(ast_ids), "unique_source_formula_ids": len(formula_ids), "formula_type_counts": dict(type_counts)}


def run(args):
    readback_path = Path(args.readback_manifest)
    zip_path = Path(args.zip)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    readback, verified_members = verify_artifact(zip_path, readback_path)

    with zipfile.ZipFile(zip_path, "r") as archive:
        names, family_by_name, selected_names, selection, feature_catalog, q90_manifest = feature_context(archive)
        member_hashes = {item["path"]: item["sha256"] for item in verified_members}
        if member_hashes["q90_formula_catalog.csv"] != EXPECTED_Q90_CATALOG_SHA256:
            raise RuntimeError("Q141_A3_BLOCKED: Q90 catalog member hash mismatch")
        if member_hashes["adaptive_novelty_feature_matrix.npz"] != EXPECTED_Q90_MATRIX_SHA256:
            raise RuntimeError("Q141_A3_BLOCKED: Q89 matrix member hash mismatch")
        if member_hashes["q90_feature_selection.json"] != EXPECTED_Q90_SELECTION_SHA256:
            raise RuntimeError("Q141_A3_BLOCKED: Q90 feature selection member hash mismatch")

        writer = ShardWriter(output_dir)
        formula_ids = set()
        ast_ids = set()
        type_counts = Counter()
        feature_usage = Counter()
        pair_usage = Counter()
        gate_usage = Counter()
        total = 0
        with archive.open("q90_formula_catalog.csv", "r") as binary:
            import io
            text_handle = io.TextIOWrapper(binary, encoding="utf-8", newline="")
            reader = csv.DictReader(text_handle)
            expected_fields = [
                "formula_id", "formula_type", "formula_size", "feature_indices",
                "features", "interaction_pair", "gate_feature", "gate_threshold",
                "weight", "search_source",
            ]
            if reader.fieldnames != expected_fields:
                raise RuntimeError("Q141_A3_BLOCKED: Q90 catalog schema mismatch")
            for row in reader:
                formula_id = row["formula_id"]
                if formula_id in formula_ids:
                    raise RuntimeError(f"Q141_A3_BLOCKED: duplicate source formula ID {formula_id}")
                formula_ids.add(formula_id)
                ast, ast_id = build_ast(row, names, family_by_name)
                if ast_id in ast_ids:
                    raise RuntimeError(f"Q141_A3_BLOCKED: duplicate canonical AST {ast_id}")
                ast_ids.add(ast_id)
                indices = [int(value) for value in row["feature_indices"].split(";")]
                for index in indices:
                    feature_usage[names[index]] += 1
                if row["formula_type"] == "pairwise_interaction":
                    pair_usage[row["interaction_pair"]] += 1
                elif row["formula_type"] == "conditional_gate":
                    gate_usage[(row["gate_feature"], row["gate_threshold"])] += 1
                record = {
                    "schema_version": "1.0",
                    "ast_id": ast_id,
                    "source_task": "Q90",
                    "source_formula_id": formula_id,
                    "output_type": "per_number_score",
                    "formula_type": row["formula_type"],
                    "formula_size": int(row["formula_size"]),
                    "source_feature_indices": indices,
                    "source_feature_names": row["features"].split("+"),
                    "search_source": row["search_source"],
                    "ast": ast,
                }
                writer.write(record)
                type_counts[row["formula_type"]] += 1
                total += 1
        writer.close()

    if total != EXPECTED_FORMULA_TOTAL or dict(type_counts) != EXPECTED_FORMULA_COUNTS:
        raise RuntimeError(f"Q141_A3_BLOCKED: formula counts mismatch {total} {dict(type_counts)}")
    if len(formula_ids) != total or len(ast_ids) != total:
        raise RuntimeError("Q141_A3_BLOCKED: formula/AST uniqueness mismatch")
    if len(pair_usage) != 190 or set(pair_usage.values()) != {153}:
        raise RuntimeError("Q141_A3_BLOCKED: pairwise interaction pair coverage mismatch")
    if len(gate_usage) != 40 or set(gate_usage.values()) != {969}:
        raise RuntimeError("Q141_A3_BLOCKED: conditional gate coverage mismatch")

    readback_summary = verify_shards(writer.shards, output_dir, total)
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-A3",
        "status": "Q90_TYPED_AST_IMPORT_COMPLETED",
        "decision": "Q90_FORMULAS_IMPORTED_AS_TYPED_PER_NUMBER_AST; NO_PREDICTIVE_CLAIM",
        "source": {
            "artifact_id": ARTIFACT_ID,
            "workflow_run_id": WORKFLOW_RUN_ID,
            "artifact_zip_sha256": EXPECTED_ZIP_SHA256,
            "q90_exact_head_sha": readback["source"]["artifact_exact_head_sha"],
            "q90_archive_git_blob_sha1": EXPECTED_Q90_ARCHIVE_BLOB,
            "q90_archive_draws": EXPECTED_Q90_ARCHIVE_DRAWS,
            "q90_archive_cutoff": EXPECTED_Q90_ARCHIVE_CUTOFF,
            "q89_feature_matrix_sha256": EXPECTED_Q90_MATRIX_SHA256,
            "q90_formula_catalog_sha256": EXPECTED_Q90_CATALOG_SHA256,
            "q90_feature_selection_sha256": EXPECTED_Q90_SELECTION_SHA256,
        },
        "feature_universe": {
            "source_namespace": "Q89",
            "total_features": len(names),
            "selected_features": len(selected_names),
            "selection_split": selection["selection_split"],
            "selection_rule": selection["selection_rule"],
            "selected_feature_names": [item["feature"] for item in selection["selected_features"]],
        },
        "formula_counts": {
            "total": total,
            "by_type": dict(type_counts),
            "pairwise_interaction_pairs": len(pair_usage),
            "gate_feature_threshold_variants": len(gate_usage),
            "unique_source_formula_ids": len(formula_ids),
            "unique_canonical_ast_ids": len(ast_ids),
            "duplicate_ast_count": total - len(ast_ids),
        },
        "ast_semantics": {
            "linear_mean": "arithmetic mean of selected per-target z-scored Q89 feature columns",
            "pairwise_interaction": "linear mean of four features plus 1/4 times candidate-wise z-score of one pairwise product",
            "conditional_gate": "linear mean of four features plus 1/4 times indicator(feature >= threshold)",
            "feature_namespace": "Q89",
            "output_type": "per_number_score",
            "rational_parameters": True,
            "commutative_canonicalization": ["mean terms sorted by feature index", "product factors sorted by feature index"],
        },
        "artifact_members_verified": len(verified_members),
        "artifact_member_readback": verified_members,
        "shards": writer.shards,
        "readback": readback_summary,
        "recovery_history": [
            {
                "run_id": 43275277890,
                "failed_stage": "Q90_manifest_schema_validation",
                "root_cause": "The Q90 formula count is nested at formula_grammar.formula_count, not at the manifest top level.",
                "recovery": "Read the nested formula grammar count, assert the declared per-type counts and feature-matrix shape/dtype, and add a unit test for the persisted manifest schema.",
            }
        ],
        "limitations": [
            "Q90 catalog covers only the 20 Discovery-selected features from the 59-feature Q89 matrix.",
            "Q90 source archive ends 2026-11-07 and contains 3,401 draws; it is not the full Q141 archive.",
            "This is a structural AST import, not a replay or validation of predictive performance.",
            "Q7 quintet-scoring formulas remain a separate output type and are not imported here.",
        ],
        "next_action": "Import Q7's 1,023 quintet-ranking formulas as a distinct AST/output type; then reconcile source windows and scoring semantics before a common-source behaviour atlas.",
    }
    report_path = output_dir / "q90_typed_ast_import_report_2026-11-12.json"
    report_bytes = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
    report_path.write_bytes(report_bytes)

    files = {}
    for path in [report_path] + [output_dir / shard["path"] for shard in writer.shards]:
        data = path.read_bytes()
        files[path.name] = {
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "git_blob_sha1": git_blob_sha1(data),
        }
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-A3",
        "status": "LOCAL_AST_IMPORT_VERIFIED_PENDING_REMOTE_GIT_READBACK",
        "artifact_id": ARTIFACT_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "artifact_zip_sha256": EXPECTED_ZIP_SHA256,
        "q90_archive_git_blob_sha1": EXPECTED_Q90_ARCHIVE_BLOB,
        "q90_feature_matrix_sha256": EXPECTED_Q90_MATRIX_SHA256,
        "q90_formula_catalog_sha256": EXPECTED_Q90_CATALOG_SHA256,
        "q90_feature_selection_sha256": EXPECTED_Q90_SELECTION_SHA256,
        "formula_total": total,
        "formula_type_counts": dict(type_counts),
        "unique_ast_count": len(ast_ids),
        "duplicate_ast_count": total - len(ast_ids),
        "shard_rows_target": SHARD_ROWS,
        "shard_count": len(writer.shards),
        "shards": writer.shards,
        "report": files[report_path.name],
        "verified_artifact_members": len(verified_members),
        "readback": readback_summary,
        "files": files,
    }
    manifest_path = output_dir / "q90_typed_ast_import_manifest_2026-11-12.json"
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha = sha256_bytes(manifest_bytes)
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-A3",
        "status": "LOCAL_AST_IMPORT_VERIFIED_PENDING_REMOTE_GIT_READBACK",
        "manifest_path": manifest_path.name,
        "manifest_sha256": manifest_sha,
        "report_path": report_path.name,
        "report_sha256": files[report_path.name]["sha256"],
        "formula_total": total,
        "unique_ast_count": len(ast_ids),
        "next_action": report["next_action"],
    }
    checkpoint_path = output_dir / "q90_typed_ast_import_checkpoint_2026-11-12.json"
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    # Final local readback includes JSON parse and exact manifest hashes.
    parsed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parsed_checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if parsed_manifest["formula_total"] != EXPECTED_FORMULA_TOTAL:
        raise RuntimeError("Q141_A3_BLOCKED: manifest JSON readback mismatch")
    if parsed_checkpoint["manifest_sha256"] != manifest_sha:
        raise RuntimeError("Q141_A3_BLOCKED: checkpoint manifest hash mismatch")
    for filename, expected in files.items():
        data = (output_dir / filename).read_bytes()
        if sha256_bytes(data) != expected["sha256"] or git_blob_sha1(data) != expected["git_blob_sha1"]:
            raise RuntimeError(f"Q141_A3_BLOCKED: final local readback mismatch {filename}")

    summary = {
        "task_id": "Q141-A3",
        "status": "LOCAL_AST_IMPORT_VERIFIED_PENDING_REMOTE_GIT_READBACK",
        "formula_total": total,
        "formula_type_counts": dict(type_counts),
        "unique_ast_count": len(ast_ids),
        "duplicate_ast_count": total - len(ast_ids),
        "shard_count": len(writer.shards),
        "artifact_members_verified": len(verified_members),
        "manifest_sha256": manifest_sha,
        "readback": readback_summary,
    }
    print(json.dumps(summary, sort_keys=True, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--readback-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
