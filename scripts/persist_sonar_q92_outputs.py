#!/usr/bin/env python3
"""Fail-closed append-only copier and checkpoint renderer for accepted Q92 outputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

TASK_ID="Q92_2026_11_08"
EXPECTED_ARCHIVE_COUNT=3402
EXPECTED_TARGETS=3352
EXPECTED_FORMULAS=8_436_285
EXPECTED_METRICS_ROWS=25_308_855
EXPECTED_HOLM_FAMILY=75_926_565
EXPECTED_SPLITS={"discovery":2012,"validation":670,"blind_oos":670}
EXPECTED_SHARDS=15

def sha256_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()

def read_json(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def fail(message:str):
    raise SystemExit("Q92_PERSIST_BLOCKED: "+message)

def validate_bundle(bundle:Path):
    prefix=bundle/"reports"/"sequence_agent"
    report_path=prefix/"q92_20261108_report.json"
    manifest_path=prefix/"q92_20261108_manifest.json"
    marker_path=prefix/"q92_20261108_acceptance_pass_marker.json"
    for path in (report_path,manifest_path,marker_path):
        if not path.is_file():
            fail("required acceptance bundle file missing: "+str(path.relative_to(bundle)))
    report=read_json(report_path)
    manifest=read_json(manifest_path)
    marker=read_json(marker_path)
    if marker.get("status")!="ACCEPTANCE_PASS_PENDING_PERSISTENCE":
        fail("acceptance marker status is not pass-pending-persistence")
    if marker.get("validator_marker")!="Q92_ACCEPTANCE_PASS":
        fail("acceptance marker lacks validator success token")
    if marker.get("report_sha256")!=sha256_file(report_path) or marker.get("manifest_sha256")!=sha256_file(manifest_path):
        fail("acceptance marker report/manifest SHA-256 mismatch")
    if report.get("task_id")!=TASK_ID or manifest.get("task_id")!=TASK_ID or marker.get("task_id")!=TASK_ID:
        fail("task identity mismatch")
    if report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION" or manifest.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        fail("report/manifest status mismatch")
    archive_sha=report.get("source_archive_sha256")
    if not archive_sha or archive_sha!=manifest.get("source_archive_sha256") or archive_sha!=marker.get("source_archive_sha256"):
        fail("canonical archive SHA-256 mismatch")
    if report.get("target_count")!=EXPECTED_ARCHIVE_COUNT or report.get("scored_targets")!=EXPECTED_TARGETS:
        fail("target/archive count mismatch")
    if report.get("formula_count")!=EXPECTED_FORMULAS or report.get("metrics_rows")!=EXPECTED_METRICS_ROWS:
        fail("formula/metric row count mismatch")
    if report.get("split_counts")!=EXPECTED_SPLITS or manifest.get("split_counts")!=EXPECTED_SPLITS:
        fail("chronological split count mismatch")
    if report.get("multiple_testing",{}).get("test_count")!=EXPECTED_HOLM_FAMILY or manifest.get("formula_split_endpoint_holm_family_size")!=EXPECTED_HOLM_FAMILY:
        fail("global Holm family size mismatch")
    if report.get("shard_count")!=EXPECTED_SHARDS or manifest.get("shard_count")!=EXPECTED_SHARDS:
        fail("shard count mismatch")
    if report.get("candidate_selection",{}).get("blind_oos_used_for_selection") is not False:
        fail("Blind OOS was not explicitly excluded from selection")
    inference=read_json(prefix/"q92_20261108_paired_inference.json")
    if inference.get("primary_decision") not in ("NO_SIGNIFICANT_GAIN","SIGNIFICANT_POSITIVE_GAIN"):
        fail("paired inference primary decision missing")
    metrics_parts=manifest.get("metrics_parts",[])
    target_parts=manifest.get("target_ledger_parts",[])
    if len(metrics_parts)!=EXPECTED_SHARDS or len(target_parts)!=EXPECTED_SHARDS:
        fail("manifest does not contain exactly 15 metric and target-ledger parts")
    expected_paths=set()
    for entry in metrics_parts:
        path=bundle/entry["path"]
        if not path.is_file() or path.stat().st_size!=entry.get("bytes") or sha256_file(path)!=entry.get("sha256"):
            fail("metrics part byte/SHA mismatch: "+str(entry.get("path")))
        expected_paths.add(entry["path"])
    for entry in target_parts:
        path=bundle/entry["path"]
        if not path.is_file() or path.stat().st_size!=entry.get("bytes") or sha256_file(path)!=entry.get("sha256"):
            fail("target-ledger part byte/SHA mismatch: "+str(entry.get("path")))
        expected_paths.add(entry["path"])
    supplemental=manifest.get("supplemental_outputs",{})
    for key in ("candidate_shortlist","candidate_selection","paired_blind_ledger","paired_inference"):
        entry=supplemental.get(key,{})
        path=bundle/entry.get("path","")
        if not path.is_file() or path.stat().st_size!=entry.get("bytes") or sha256_file(path)!=entry.get("sha256"):
            fail("supplemental output byte/SHA mismatch: "+key)
        expected_paths.add(entry["path"])
    expected_paths.update((str(report_path.relative_to(bundle)),str(manifest_path.relative_to(bundle)),str(marker_path.relative_to(bundle))))
    files=[]
    for path in sorted((bundle/"reports"/"sequence_agent").rglob("*")):
        if not path.is_file():
            continue
        relative=str(path.relative_to(bundle))
        if not relative.startswith("reports/sequence_agent/q92_20261108_"):
            fail("unexpected artifact file in accepted bundle: "+relative)
        if relative.endswith("acceptance_raw_pvalues_temp.bin"):
            fail("temporary raw p-value vector must not be persisted")
        if relative not in expected_paths:
            fail("accepted bundle contains unmanifested file: "+relative)
        files.append({"path":relative,"bytes":path.stat().st_size,"sha256":sha256_file(path)})
    if set(item["path"] for item in files)!=expected_paths:
        fail("accepted bundle file coverage differs from manifest")
    return report,manifest,marker,inference,files

def render_checkpoint(report,manifest,marker,inference,files):
    selected=report["candidate_selection"]["selected_candidate_id"]
    q89=report["candidate_selection"]["Q89_control_candidate_id"]
    q92metrics=report["selected_candidate_metrics"]["Q92_candidate"]["blind_oos_descriptive_only"]
    q89metrics=report["selected_candidate_metrics"]["Q89_control"]["blind_oos_descriptive_only"]
    primary_name=inference["multiple_testing"]["endpoints"][0]
    primary=inference["endpoints"][primary_name]
    payload={
        "schema_version":"1.0","task_id":TASK_ID,"status":"PERSISTED_PENDING_HUMAN_REVIEW",
        "acceptance_status":"ACCEPTANCE_PASS_PENDING_PERSISTENCE",
        "source_archive_sha256":report["source_archive_sha256"],
        "source_archive_git_blob_sha1":report["source_archive_git_blob_sha1"],
        "source_checkout_sha":marker.get("source_commit"),
        "github_actions_run_id":marker.get("run_id"),
        "target_count":report["target_count"],"scored_targets":report["scored_targets"],
        "formula_count":report["formula_count"],"metrics_rows":report["metrics_rows"],
        "split_counts":report["split_counts"],
        "holm_family_size":report["multiple_testing"]["test_count"],
        "holm_adjusted_formula_split_rows_below_0_05":report["multiple_testing"]["holm_adjusted_formula_split_rows_below_0_05"],
        "minimum_holm_p_max_endpoint_family":report["multiple_testing"]["minimum_holm_p_max_endpoint_family"],
        "selected_q92_candidate_id":selected,"q89_control_candidate_id":q89,
        "blind_oos_metrics_descriptive_only":{"Q92":q92metrics,"Q89":q89metrics},
        "paired_blind_inference":{"primary_endpoint":primary_name,"primary_decision":inference["primary_decision"],"summary":primary,
            "multiple_testing":inference["multiple_testing"]},
        "persisted_output_files":files,
        "limitations":report.get("limitations",[]),
        "next_action":"Human review of the accepted Q92 catalog, frozen candidate and paired Blind OOS inference; no engine promotion or merge without approval."
    }
    md=[
        "# VinciCasa SONAR Q92 — persisted acceptance checkpoint",
        "",
        "**Status: PERSISTED_PENDING_HUMAN_REVIEW. No engine was promoted.**",
        "",
        f"- Canonical archive SHA-256: `{payload['source_archive_sha256']}`",
        f"- Archive Git blob SHA-1: `{payload['source_archive_git_blob_sha1']}`",
        f"- Target count / scored targets: {payload['target_count']} / {payload['scored_targets']}",
        f"- Formula universe: {payload['formula_count']:,}; metric rows: {payload['metrics_rows']:,}",
        f"- Discovery / Validation / Blind OOS: {payload['split_counts']}",
        f"- Global Holm family: {payload['holm_family_size']:,}; formula/split rows below 0.05: {payload['holm_adjusted_formula_split_rows_below_0_05']}",
        f"- Frozen Q92 candidate: `{selected}`",
        f"- Same-archive Q89 control: `{q89}`",
        "",
        "## Blind OOS (descriptive only)",
        "",
        "| Endpoint | Q92 | Q89 control |",
        "|---|---:|---:|",
        f"| Top-5 hit share | {float(q92metrics['mean_number_hits_top5']):.6%} | {float(q89metrics['mean_number_hits_top5']):.6%} |",
        f"| Top-10 hit share | {float(q92metrics['mean_number_hits_top10']):.6%} | {float(q89metrics['mean_number_hits_top10']):.6%} |",
        f"| Top-20 hit share | {float(q92metrics['mean_number_hits_top20']):.6%} | {float(q89metrics['mean_number_hits_top20']):.6%} |",
        f"| Mean rank | {float(q92metrics['mean_rank_of_actual_numbers']):.6f} | {float(q89metrics['mean_rank_of_actual_numbers']):.6f} |",
        "",
        "## Paired Blind OOS inference",
        "",
        f"- Primary endpoint: {primary_name}",
        f"- Decision: **{inference['primary_decision']}**",
        f"- Mean delta: {float(primary['mean_delta']):.6%}",
        f"- Block-bootstrap 95% CI: [{float(primary['bootstrap_ci_95_low']):.6%}, {float(primary['bootstrap_ci_95_high']):.6%}]",
        f"- Sign-flip raw p: {float(primary['signflip_p_raw']):.8g}; Holm p: {float(primary['signflip_p_holm']):.8g}",
        f"- Paired target count: {primary['n_targets']}; block length: {inference['block_length']}; replicates: {inference['replicates']}",
        "",
        "## Limitations and next action",
        "",
        *[f"- {item}" for item in payload["limitations"]],
        f"- {payload['next_action']}",
        "",
        "This checkpoint does not authorize merge, engine promotion, or shadow insertion."
    ]
    return payload,"\n".join(md)+"\n"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-dir",type=Path,required=True)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    root=args.root.resolve()
    bundle=args.bundle_dir.resolve()
    report,manifest,marker,inference,files=validate_bundle(bundle)
    for item in files:
        source=bundle/item["path"]
        target=root/item["path"]
        if target.exists():
            fail("append-only target already exists: "+item["path"])
    checkpoint_json=root/"reports"/"sequence_agent"/"q92_20261108_persistence_checkpoint.json"
    checkpoint_md=root/"reports"/"sequence_agent"/"q92_20261108_persistence_checkpoint.md"
    if checkpoint_json.exists() or checkpoint_md.exists():
        fail("persistence checkpoint path already exists")
    for item in files:
        source=bundle/item["path"]
        target=root/item["path"]
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        if target.stat().st_size!=item["bytes"] or sha256_file(target)!=item["sha256"]:
            fail("copy byte/SHA readback mismatch: "+item["path"])
    payload,markdown=render_checkpoint(report,manifest,marker,inference,files)
    payload["dry_run"]=bool(args.dry_run)
    checkpoint_json.parent.mkdir(parents=True,exist_ok=True)
    checkpoint_json.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    checkpoint_md.write_text(markdown,encoding="utf-8")
    result={
        "status":"PERSISTED_PENDING_HUMAN_REVIEW" if not args.dry_run else "DRY_RUN_PERSISTED_PENDING_HUMAN_REVIEW",
        "task_id":TASK_ID,"files_copied":len(files),"checkpoint_json":str(checkpoint_json.relative_to(root)),
        "checkpoint_json_sha256":sha256_file(checkpoint_json),"checkpoint_md":str(checkpoint_md.relative_to(root)),
        "checkpoint_md_sha256":sha256_file(checkpoint_md),"source_archive_sha256":report["source_archive_sha256"],
        "selected_q92_candidate_id":report["candidate_selection"]["selected_candidate_id"],
        "paired_primary_decision":inference["primary_decision"]
    }
    print("Q92_PERSIST_OUTPUTS_BEGIN")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    print("Q92_PERSIST_OUTPUTS_END")

if __name__=="__main__":
    main()
