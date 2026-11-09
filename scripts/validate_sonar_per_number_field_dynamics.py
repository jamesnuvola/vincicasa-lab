#!/usr/bin/env python3
"""Fail-closed replay validator for Q84 per-number field dynamics."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import sonar_strategy_atlas as q84
from sonar_sequence_agent import MIN_HISTORY
import sonar_per_number_field_dynamics as field

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"


def fail(message): raise SystemExit("Q84_FIELD_ACCEPTANCE_BLOCKED: "+str(message))


def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()


def close(a,b,label):
    try: x,y=float(a),float(b)
    except Exception: fail(label+" is not numeric")
    if not math.isfinite(x) or not math.isfinite(y) or abs(x-y)>1e-12:
        fail(label+" mismatch: "+repr(x)+" != "+repr(y))


def compare_metrics(observed,expected):
    if len(observed)!=len(expected): fail("metric row count mismatch")
    lookup={(x["strategy_id"],x["split"]):x for x in observed}
    if len(lookup)!=len(expected): fail("duplicate metric row")
    for want in expected:
        key=(want["strategy_id"],want["split"]); got=lookup.get(key)
        if got is None: fail("missing metric "+repr(key))
        for name in ("targets","top20_4plus","top20_5of5","top20_hit_distribution"):
            if got.get(name)!=want.get(name): fail(repr(key)+" "+name+" mismatch")
        for name in ("mean_hits_top5","mean_hits_top10","mean_hits_top20","mean_rank_actual_numbers","top20_5of5_rate"):
            close(got.get(name),want.get(name),repr(key)+" "+name)
        for family in ("p_values_raw","p_values_holm"):
            for endpoint in ("top5","top10","top20"):
                close(got[family][endpoint],want[family][endpoint],repr(key)+" "+family+"/"+endpoint)


def validate(write_validation):
    protocol_path=OUT/"q84_per_number_field_protocol_2026-11-09.json"
    catalog_path=OUT/"q84_per_number_field_catalog.jsonl"
    ledger_path=OUT/"q84_per_number_field_target_ledger.csv.gz"
    report_path=OUT/"q84_per_number_field_report.json"
    manifest_path=OUT/"q84_per_number_field_manifest.json"
    checkpoint_path=OUT/"q84_per_number_field_checkpoint_2026-11-09.json"
    validation_path=OUT/"q84_per_number_field_validation.json"
    protocol=json.loads(protocol_path.read_text(encoding="utf-8"))
    report=json.loads(report_path.read_text(encoding="utf-8"))
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    raw=field.ARCHIVE.read_bytes()
    sha256=hashlib.sha256(raw).hexdigest(); sha1=q84.git_blob_sha1(field.ARCHIVE)
    if sha256!=field.EXPECTED_SHA256 or sha1!=field.EXPECTED_SHA1: fail("canonical archive SHA mismatch")
    if protocol["source_archive"]["sha256"]!=sha256 or protocol["source_archive"]["git_blob_sha1"]!=sha1: fail("protocol/archive mismatch")
    if report["source_archive"]["sha256"]!=sha256 or report["source_archive"]["git_blob_sha1"]!=sha1: fail("report/archive mismatch")
    if manifest.get("target_count")!=field.EXPECTED_TARGETS or manifest.get("holm_tests")!=126: fail("manifest dimensions mismatch")
    catalog=[json.loads(x) for x in catalog_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if [x["strategy_id"] for x in catalog]!=list(field.MODEL_IDS): fail("catalog/model order mismatch")

    result=field.compute_experiment()
    if len(result["tests"])!=126: fail("global Holm family size mismatch")
    compare_metrics(report.get("metrics",[]),result["metrics"])
    if report.get("selected_on_discovery_only")!=result["selected_id"]: fail("Discovery-only selection replay mismatch")
    if report.get("split_counts")!=result["split_counts"]: fail("split count mismatch")

    rows_seen=0
    with gzip.open(ledger_path,"rt",newline="",encoding="utf-8") as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=field.ledger_fields(): fail("target ledger schema mismatch")
        for t,row in enumerate(reader):
            if t>=field.EXPECTED_TARGETS: fail("extra target ledger row")
            i=MIN_HISTORY+t
            if row["target_date"]!=result["dates"][i] or row["cutoff_date"]!=result["dates"][i-1]:
                fail("target/cutoff mismatch at row "+str(t))
            if int(row["prior_draws"])!=i: fail("prior count mismatch at row "+str(t))
            if row["actual_quintet"]!=" ".join(map(str,result["draws"][i]["nums"])): fail("actual quintet mismatch at row "+str(t))
            if row["split"]!=result["splits"][t]: fail("split mismatch at row "+str(t))
            if row["field_state_sha256"]!=result["signatures"][t]: fail("field signature mismatch at row "+str(t))
            for mi,model in enumerate(field.MODEL_IDS):
                ranks=np.asarray([int(row[f"rank_{field.slug(model)}_{n:02d}"]) for n in range(1,41)],dtype=np.int16)
                if sorted(ranks.tolist())!=list(range(1,41)): fail("non-permutation rank vector at row "+str(t))
                if not np.array_equal(ranks,result["ranks"][t,mi]): fail("rank replay mismatch "+model+" row "+str(t))
            rows_seen+=1
    if rows_seen!=field.EXPECTED_TARGETS: fail("ledger row count mismatch")

    for key,path in (("catalog",catalog_path),("target_ledger",ledger_path),("report",report_path)):
        item=manifest.get("files",{}).get(key,{})
        if item.get("path")!=str(path.relative_to(ROOT)) or item.get("sha256")!=sha256_file(path) or item.get("bytes")!=path.stat().st_size:
            fail("manifest byte/SHA mismatch: "+key)

    checks={"canonical_draws":len(result["draws"]),"targets":rows_seen,"strict_prior_cutoffs":rows_seen,
      "rank_vectors_replayed":rows_seen*len(field.MODEL_IDS),"models":len(field.MODEL_IDS),
      "field_candidates":len(field.FIELD_IDS),"holm_family_tests":len(result["tests"]),
      "discovery_selection_replayed":result["selected_id"],"archive_sha256":sha256}
    receipt={"status":"PASS","task_id":"Q84-FIELD-DYNAMICS-01","validated_at_utc":datetime.now(timezone.utc).isoformat(),
      "checks":checks,"scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "human_review_required":True,"engine_promotion_allowed":False,"immutable_freezes_modified":False}
    if write_validation:
        report["status"]="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW"
        report["acceptance_validation"]={"status":"PASS","artifact":str(validation_path.relative_to(ROOT))}
        field.json_dump(report_path,report)
        manifest["status"]="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW"
        manifest["files"]["report"]["sha256"]=sha256_file(report_path)
        manifest["files"]["report"]["bytes"]=report_path.stat().st_size
        manifest["acceptance_validation"]={"status":"PASS","rank_vectors_replayed":rows_seen*len(field.MODEL_IDS)}
        field.json_dump(manifest_path,manifest)
        checkpoint=json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["status"]="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW"
        checkpoint["validation_checks"]=checks
        checkpoint["next_action"]="Human review; then preregister a genuinely prospective confirmation without changing historical freezes."
        field.json_dump(checkpoint_path,checkpoint)
        field.json_dump(validation_path,receipt)
    else:
        if report.get("status")!="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW": fail("persisted report status invalid")
        if manifest.get("status")!="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW": fail("persisted manifest status invalid")
        if not validation_path.is_file() or json.loads(validation_path.read_text()).get("status")!="PASS": fail("validation receipt missing")
        if json.loads(checkpoint_path.read_text()).get("status")!="VALIDATED_HISTORICAL_EXPLORATORY_PENDING_HUMAN_REVIEW": fail("checkpoint status invalid")
    print("SONAR_Q84_FIELD_ACCEPTANCE_BEGIN")
    print(json.dumps(receipt,sort_keys=True,separators=(",",":")))
    print("SONAR_Q84_FIELD_ACCEPTANCE_END")
    return receipt


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args()
    validate(write_validation=not args.read_only)
