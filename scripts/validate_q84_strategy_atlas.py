#!/usr/bin/env python3
"""Fail-closed Q84 output acceptance against canonical archive and exact Git blob checksums."""
from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"reports/sequence_agent";ARCH=ROOT/"data/storico_daily.csv";ALPHA="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
def gitsha(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def fail(msg):raise SystemExit("Q84_VALIDATION_FAILED: "+msg)
def main():
    with ARCH.open(newline="",encoding="utf-8") as f:ar=list(csv.reader(f))
    dates=[r[0] for r in ar[1:]];draws=[[int(x) for x in r[1:6]] for r in ar[1:]];N=len(draws);T=N-50
    paths={k:OUT/f"strategy_atlas_{k}" for k in ("report.json","catalog.jsonl","target_ledger.csv","lifecycle.json")}
    if any(not p.is_file() for p in paths.values()):fail("missing Q84 artifact")
    report=json.loads(paths["report.json"].read_text());catalog=[json.loads(x) for x in paths["catalog.jsonl"].read_text().splitlines()];life=json.loads(paths["lifecycle.json"].read_text())
    source=gitsha(ARCH.read_bytes())
    if report.get("status")!="EXPLORATORY_COMPLETE_PENDING_HUMAN_REVIEW" or report.get("review_status")!="PENDING_HUMAN_REVIEW":fail("report status/review gate mismatch")
    if report.get("source_archive_blob_sha")!=source or life.get("source_archive_blob_sha")!=source:fail("archive SHA mismatch")
    if report.get("archive",{}).get("draw_count")!=N or report.get("archive",{}).get("last_date")!=dates[-1]:fail("archive cutoff mismatch")
    if report.get("archive",{}).get("eligible_target_count")!=T or report.get("finite_grammar",{}).get("catalog_records")!=730:fail("target/catalog cardinality mismatch")
    if len(catalog)!=730 or len({x.get("strategy_id") for x in catalog})!=730:fail("catalog rows/IDs not unique")
    fam={"SINGLE_FEATURE":27,"UNION_OF_SINGLE_TOP5":351,"EQUAL_WEIGHT_PAIR_COMPOSITE":351,"RETROSPECTIVE_META_STRATEGY":1}
    for name,count in fam.items():
        if sum(x.get("family")==name for x in catalog)!=count:fail("catalog family count mismatch: "+name)
    if life.get("strategy_count")!=730 or len(life.get("strategies",[]))!=730:fail("lifecycle cardinality mismatch")
    ix=list(range(T));counts={"discovery":sum(t/T<.6 for t in ix),"validation":sum(.6<=t/T<.8 for t in ix),"blind_oos":sum(t/T>=.8 for t in ix)}
    if report.get("split_counts")!=counts:fail("split count mismatch")
    with paths["target_ledger.csv"].open(newline="",encoding="utf-8") as f:ledger=list(csv.DictReader(f))
    if len(ledger)!=T:fail("target ledger row count mismatch")
    rank_cols=[c for c in ledger[0] if c.startswith("rank_vector_")];actual_cols=[c for c in ledger[0] if c.startswith("actual_ranks_")]
    if len(rank_cols)!=51 or len(actual_cols)!=51:fail("rank vector strategy dimensions mismatch")
    union_cols=[c for c in ledger[0] if c.startswith("candidate_union_numbers_")]
    if len(union_cols)!=12:fail("union candidate columns mismatch")
    for t,row in enumerate(ledger):
        i=t+50;actual=draws[i]
        if row["target_date"]!=dates[i] or row["cutoff_date"]!=dates[i-1] or int(row["prior_draws"])!=i:fail(f"target cutoff reconciliation mismatch at {i}")
        if [int(x) for x in row["actual_quintet"].split()]!=actual:fail(f"actual quintet mismatch at {i}")
        split="discovery" if t/T<.6 else "validation" if t/T<.8 else "blind_oos"
        if row["split"]!=split:fail(f"split label mismatch at {i}")
        for rc in rank_cols:
            v=row[rc];ac="actual_ranks_"+rc[len("rank_vector_"):]
            if len(v)!=40 or set(v)!=set(ALPHA):fail(f"rank permutation invalid at {i}/{rc}")
            if row[ac]!="".join(v[n-1] for n in actual):fail(f"actual ranks fail reconciliation at {i}/{rc}")
        for uc in union_cols:
            nums=[ALPHA.index(ch)+1 for ch in row[uc]];suf=uc[len("candidate_union_numbers_"):];size=int(row["candidate_union_size_"+suf]);h=int(row["candidate_union_actual_hits_"+suf]);ex=float(row["candidate_union_expected_hits_"+suf])
            if not 5<=len(nums)<=10 or len(set(nums))!=len(nums) or size!=len(nums):fail(f"union size mismatch at {i}/{uc}")
            if h!=sum(n in nums for n in actual) or abs(ex-5*size/40)>1e-12:fail(f"union target metric mismatch at {i}/{uc}")
    sums=report.get("artifact_checksums",{})
    for fn,key in [("catalog.jsonl","strategy_atlas_catalog_jsonl"),("target_ledger.csv","strategy_atlas_target_ledger_csv"),("lifecycle.json","strategy_atlas_lifecycle_json")]:
        if sums.get(key)!=gitsha(paths[fn].read_bytes()):fail("persisted artifact checksum mismatch: "+fn)
    mt=report.get("multiple_testing",{})
    expected={"performance_family_tests":4536,"pair_union_conditional_hypergeometric_tests":1053,"pair_gain_analytic_normal_tests":1053,"conditional_state_tests":153,"selected_pair_block_bootstrap_tests":48}
    for k,v in expected.items():
        if mt.get(k)!=v:fail("multiple-testing family size mismatch: "+k)
    print(json.dumps({"status":"PASS","archive_draws":N,"archive_last_date":dates[-1],"targets":T,"split_counts":report["split_counts"],"catalog_records":len(catalog),"rank_vector_strategies":len(rank_cols),"ledger_rows":len(ledger),"ledger_columns":len(ledger[0]),"family_sizes":expected,"artifact_checksums":sums},separators=(",",":")))
if __name__=="__main__":main()
