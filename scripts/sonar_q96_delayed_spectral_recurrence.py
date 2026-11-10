#!/usr/bin/env python3
"""Q96: delayed recurrence of prior-only leading spectral subspaces."""
from __future__ import annotations
import csv, gzip, hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import sonar_q87_node_graph_phase_lag as q87
import sonar_q90_edge_field_decomposition as q90
import sonar_q93_spectral_coherence as q93
import sonar_q94_spectral_subspace_persistence as q94
import sonar_q95_subspace_permutation_null as q95

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
PROTOCOL=OUT/"q96_delayed_spectral_recurrence_protocol_2026-11-10.json"
CATALOG=OUT/"q96_delayed_spectral_recurrence_catalog.jsonl"
LEDGER=OUT/"q96_delayed_spectral_recurrence_target_ledger.csv.gz"
REPORT=OUT/"q96_delayed_spectral_recurrence_report.json"
MANIFEST=OUT/"q96_delayed_spectral_recurrence_manifest.json"
CHECKPOINT=OUT/"q96_delayed_spectral_recurrence_checkpoint_2026-11-10.md"
VALIDATION=OUT/"q96_delayed_spectral_recurrence_validation.json"
TASK_ID="Q96-DELAYED-SPECTRAL-RECURRENCE-01"
MIN_HISTORY=q94.MIN_HISTORY
MODES=q94.REQUESTED_MODES
LAGS=(2,3,5)
PERM_COUNT=999
PERM_SEED=9601
BLOCK=20
REPS=2000
SPLITS=("discovery","validation","blind_oos")
EXPECTED_COUNTS={"discovery":1921,"validation":641,"blind_oos":641}

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def git_blob_sha1(path):
    data=path.read_bytes()
    h=hashlib.sha1()
    h.update(b"blob "+str(len(data)).encode("ascii")+b"\0")
    h.update(data)
    return h.hexdigest()

def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")

def fixed_permutations():
    rng=np.random.default_rng(PERM_SEED)
    identity=tuple(range(40)); seen=set(); out=[]
    while len(out)<PERM_COUNT:
        p=tuple(map(int,rng.permutation(40)))
        if p!=identity and p not in seen:
            seen.add(p); out.append(p)
    a=np.asarray(out,dtype=np.int16)
    if a.shape!=(PERM_COUNT,40):
        raise ValueError("Q96 fixed permutation shape mismatch")
    return a

def reference_index(offset,lag):
    offset=int(offset); lag=int(lag)
    if lag not in LAGS or offset<0:
        raise ValueError("Q96 invalid offset or lag")
    return offset-lag if offset>=lag else None

def verify_sources():
    manifest=json.loads(q95.MANIFEST.read_text(encoding="utf-8"))
    validation=json.loads(q95.VALIDATION.read_text(encoding="utf-8"))
    report=json.loads(q95.REPORT.read_text(encoding="utf-8"))
    protocol=json.loads(q95.PROTOCOL.read_text(encoding="utf-8"))
    if manifest.get("status")!="ACCEPTANCE_PASS" or validation.get("status")!="PASS":
        raise ValueError("Q96 blocked: Q95 source is not accepted")
    if report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW":
        raise ValueError("Q96 blocked: Q95 report status is not accepted")
    if report.get("acceptance",{}).get("validator")!="Q95_FORMULA_ACCEPTANCE_PASS":
        raise ValueError("Q96 blocked: Q95 independent acceptance marker missing")
    if git_blob_sha1(q95.MANIFEST)!="d681eedd41e3dfdec96a296d47b5330579f97847":
        raise ValueError("Q96 Q95 manifest Git blob identity mismatch")
    if git_blob_sha1(q95.VALIDATION)!="2ca7e9a289bebed2e7c25e3b65a178f721dd47fb":
        raise ValueError("Q96 Q95 validation Git blob identity mismatch")
    for key in ("catalog","target_ledger","report","protocol","checkpoint","validation"):
        meta=manifest.get("files",{}).get(key)
        if not meta:
            raise ValueError("Q96 Q95 manifest missing "+key)
        p=ROOT/meta["path"]
        if not p.is_file() or p.stat().st_size!=meta["bytes"] or sha(p)!=meta["sha256"]:
            raise ValueError("Q96 Q95 source artifact hash mismatch: "+key)
    if protocol.get("task_id")!="Q95-SPECTRAL-SUBSPACE-PERMUTATION-NULL-01":
        raise ValueError("Q96 Q95 protocol identity mismatch")
    q95.verify_sources()
    return sha(q95.MANIFEST),sha(q95.VALIDATION),sha(q95.REPORT)

def compute_bases(draws):
    """Build V_i from draws[:i] only; no target outcome is accessed."""
    bases=[]
    previous_edge=None
    for draw_index in range(MIN_HISTORY,len(draws)):
        history=draws[:draw_index]
        edge=q87.field.pair_residual_graph(history)
        if previous_edge is None:
            vectors=np.zeros((40,0),dtype=np.float64)
        else:
            _,pair_residual,_=q90.decompose_edge_change(edge-previous_edge)
            _,vectors,_=q93.spectral_modes(pair_residual,MODES)
        if vectors.ndim!=2 or vectors.shape[0]!=40 or not np.isfinite(vectors).all():
            raise ValueError("Q96 invalid spectral basis at prefix "+str(draw_index))
        if vectors.shape[1] and np.max(np.abs(vectors.T@np.ones(40)))>1e-8:
            raise ValueError("Q96 basis left all-ones-orthogonal subspace")
        bases.append(vectors.copy())
        previous_edge=edge
    return bases

def ledger_fields():
    fields=["target_date","cutoff_date","prior_draws","split"]
    for lag in LAGS:
        prefix=f"lag_{lag}"
        fields.extend([f"{prefix}_reference_prior_draws",f"{prefix}_reference_cutoff",
                       f"{prefix}_current_modes",f"{prefix}_reference_modes",
                       f"{prefix}_observed_overlap",f"{prefix}_permutation_mean",
                       f"{prefix}_permutation_sd",f"{prefix}_permutation_q95"])
        fields.extend(f"{prefix}_perm_{p:04d}" for p in range(PERM_COUNT))
    return fields

def make_ledger_row(result,offset):
    draw_index=MIN_HISTORY+offset
    dates=result["dates"]
    row={"target_date":dates[draw_index],"cutoff_date":dates[draw_index-1],
         "prior_draws":str(draw_index),"split":result["labels"][offset]}
    for li,lag in enumerate(LAGS):
        j=reference_index(offset,lag)
        reference_prior=draw_index-lag if j is not None else 0
        reference_cutoff=dates[reference_prior-1] if j is not None else ""
        values=result["permutation_values"][li][offset]
        row.update({
          f"lag_{lag}_reference_prior_draws":str(reference_prior),
          f"lag_{lag}_reference_cutoff":reference_cutoff,
          f"lag_{lag}_current_modes":str(int(result["current_modes"][offset])),
          f"lag_{lag}_reference_modes":str(int(result["reference_modes"][li][offset])),
          f"lag_{lag}_observed_overlap":format(float(result["observed"][li][offset]),".17g"),
          f"lag_{lag}_permutation_mean":format(float(values.mean()),".17g"),
          f"lag_{lag}_permutation_sd":format(float(values.std(ddof=1)),".17g"),
          f"lag_{lag}_permutation_q95":format(float(np.quantile(values,.95)),".17g")
        })
        row.update({f"lag_{lag}_perm_{p:04d}":format(float(v),".17g") for p,v in enumerate(values)})
    return row

def compute_experiment(draws=None):
    draws=q87.read_draws() if draws is None else draws
    dates=[d["date"].isoformat() for d in draws]
    archive_sha1=q90.q84.git_blob_sha1(ARCHIVE)
    archive_sha256=sha(ARCHIVE)
    if archive_sha1!=q94.EXPECTED_SHA1 or archive_sha256!=q94.EXPECTED_SHA256:
        raise ValueError("Q96 canonical archive byte identity mismatch")
    if len(draws)!=q94.EXPECTED_DRAWS or dates[0]!=q94.EXPECTED_FIRST or dates[-1]!=q94.EXPECTED_LAST:
        raise ValueError("Q96 canonical archive count/date mismatch")
    q95_manifest_sha,q95_validation_sha,q95_report_sha=verify_sources()
    total=len(draws)-MIN_HISTORY
    labels=q93.split_labels(total)
    counts=dict(Counter(labels))
    if total!=3203 or counts!=EXPECTED_COUNTS:
        raise ValueError("Q96 target/split mismatch: "+str(counts))
    bases=compute_bases(draws)
    if len(bases)!=total:
        raise ValueError("Q96 basis sequence length mismatch")
    # Independent consistency check: Q94's one-step sequence must match these same prefix bases.
    q94_stability,q94_current_modes,q94_previous_modes=q94.compute_stability(draws)
    lag1=np.zeros(total,dtype=np.float64)
    current_modes=np.asarray([b.shape[1] for b in bases],dtype=np.int16)
    previous_modes=np.zeros(total,dtype=np.int16)
    for off in range(total):
        if off>0:
            lag1[off]=q94.subspace_overlap(bases[off],bases[off-1])
            previous_modes[off]=bases[off-1].shape[1]
    if not np.allclose(lag1,q94_stability,atol=1e-12,rtol=0):
        raise ValueError("Q96 basis sequence does not reproduce Q94 lag-1 stability")
    if not np.array_equal(current_modes,q94_current_modes) or not np.array_equal(previous_modes,q94_previous_modes):
        raise ValueError("Q96 basis mode counts do not reproduce Q94")
    perms=fixed_permutations()
    observed=[]; permutation_values=[]; reference_modes=[]
    for lag in LAGS:
        obs=np.zeros(total,dtype=np.float64)
        pv=np.zeros((total,PERM_COUNT),dtype=np.float64)
        rm=np.zeros(total,dtype=np.int16)
        for off in range(total):
            j=reference_index(off,lag)
            current=bases[off]
            reference=bases[j] if j is not None else np.zeros((40,0),dtype=np.float64)
            rm[off]=reference.shape[1]
            obs[off]=q94.subspace_overlap(current,reference)
            pv[off]=q95.overlap_many(current,reference,perms)
        observed.append(obs)
        permutation_values.append(pv)
        reference_modes.append(rm)
    indices={s:np.asarray([i for i,l in enumerate(labels) if l==s],dtype=np.int64) for s in SPLITS}
    tests=[]; summaries=[]
    for li,lag in enumerate(LAGS):
        for si,split in enumerate(SPLITS):
            ix=indices[split]
            x=observed[li][ix]
            null=permutation_values[li][ix]
            null_means=null.mean(axis=0)
            target_null=null.mean(axis=1)
            excess=x-target_null
            p_raw=(1.0+float(np.sum(null_means>=x.mean())))/(1.0+PERM_COUNT)
            test_id=f"Q96|LAG{lag}|{split}"
            tests.append({"test_id":test_id,"p_raw":p_raw})
            ci=q95.bootstrap_ci(excess,seed=96010+li*100+si)
            summaries.append({
              "lag":lag,"split":split,"targets":int(len(ix)),
              "observed_overlap_mean":float(x.mean()),
              "observed_overlap_median":float(np.median(x)),
              "permutation_null_mean":float(null_means.mean()),
              "permutation_null_sd":float(null_means.std(ddof=1)),
              "permutation_null_q95":float(np.quantile(null_means,.95)),
              "mean_observed_minus_target_null":float(excess.mean()),
              "excess_block_bootstrap_ci95":ci,
              "permutation_p_raw":p_raw,
              "mean_current_modes":float(current_modes[ix].mean()),
              "mean_reference_modes":float(reference_modes[li][ix].mean()),
              "missing_reference_count":int(np.sum(reference_modes[li][ix]==0)),
              "permutation_count":PERM_COUNT
            })
    adjusted=q95.holm(tests)
    for t in tests:
        t["p_holm"]=adjusted[t["test_id"]]
    for row in summaries:
        row["permutation_p_holm"]=adjusted[f"Q96|LAG{row['lag']}|{row['split']}"]
    supported=[]
    for lag in LAGS:
        pair=[r for r in summaries if r["lag"]==lag and r["split"] in ("validation","blind_oos")]
        if len(pair)==2 and all(r["mean_observed_minus_target_null"]>0 and
                                r["excess_block_bootstrap_ci95"][0]>0 and
                                r["permutation_p_holm"]<0.05 for r in pair):
            supported.append(lag)
    gate={"status":"RECURRENCE_SUPPORTED" if supported else "NOT_SUPPORTED",
          "supported_lags":supported,"required_splits":["validation","blind_oos"],
          "global_holm_family_size":len(tests),"engine_promotion_allowed":False}
    q95_report=json.loads(q95.REPORT.read_text(encoding="utf-8"))
    return {"dates":dates,"labels":labels,"counts":counts,"bases":bases,
            "current_modes":current_modes,"observed":observed,
            "permutation_values":permutation_values,"reference_modes":reference_modes,
            "split_results":summaries,"holm_tests":tests,"primary_gate":gate,
            "archive_sha1":archive_sha1,"archive_sha256":archive_sha256,
            "q95_manifest_sha256":q95_manifest_sha,"q95_validation_sha256":q95_validation_sha,
            "q95_report_sha256":q95_report_sha,"q95_lag1_reference":q95_report.get("split_results",[])}

def write_outputs(result):
    for p in (CATALOG,LEDGER,REPORT,MANIFEST,CHECKPOINT,VALIDATION):
        if p.exists():
            raise SystemExit("Q96 append-only output exists: "+str(p.relative_to(ROOT)))
    proto=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if proto.get("task_id")!=TASK_ID or proto.get("status")!="PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q96 protocol identity/status mismatch")
    if proto.get("lags")!=list(LAGS) or proto.get("permutation_count")!=PERM_COUNT or proto.get("permutation_seed")!=PERM_SEED:
        raise ValueError("Q96 protocol frozen parameters mismatch")
    entries=[{"id":f"LAG_{lag}","role":"strict-prior current-vs-lagged leading k=2 subspace overlap","lag":lag}
             for lag in LAGS]
    entries.append({"id":"CONSTRAINED_NODE_LABEL_NULL","role":"999 fixed node-label permutations of the lagged basis"})
    with CATALOG.open("w",encoding="utf-8") as f:
        for row in entries:
            f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=ledger_fields())
                writer.writeheader()
                for off in range(len(result["labels"])):
                    writer.writerow(make_ledger_row(result,off))
    report={
      "task_id":TASK_ID,"status":"COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
      "scope":"HISTORICAL_GEOMETRIC_DIAGNOSTIC_NOT_PREDICTIVE_OR_PROSPECTIVE_CONFIRMATION",
      "source_archive":{"draws":q94.EXPECTED_DRAWS,"first_date":q94.EXPECTED_FIRST,"last_date":q94.EXPECTED_LAST,
                        "git_blob_sha1":result["archive_sha1"],"sha256":result["archive_sha256"]},
      "accepted_q95_sources":{"manifest_sha256":result["q95_manifest_sha256"],
                              "validation_sha256":result["q95_validation_sha256"],
                              "report_sha256":result["q95_report_sha256"]},
      "target_design":{"targets":len(result["labels"]),"minimum_prior_draws":MIN_HISTORY,
                       "split_counts":result["counts"],
                       "cutoff_rule":"Current subspace uses draws[:i]; lagged subspace uses draws[:i-lag]; both strictly precede target i."},
      "hypothesis":"At least one preregistered lag in {2,3,5} has label-aligned leading k=2 overlap greater than the constrained node-label permutation null in both Validation and historical Blind OOS.",
      "frozen_parameters":{"lags":list(LAGS),"requested_modes":MODES,"permutation_count":PERM_COUNT,
                           "permutation_seed":PERM_SEED,"bootstrap_block_length":BLOCK,
                           "bootstrap_replicates":REPS,"multiple_testing":"one global Holm family of nine lag-by-split tests"},
      "split_results":result["split_results"],"global_holm_tests":result["holm_tests"],
      "primary_gate":result["primary_gate"],"q95_lag1_reference":result["q95_lag1_reference"],
      "guardrails":["strict-prior prefixes only","no target outcome values read","permutations inferential only",
                    "one global Holm family of nine tests","historical Blind OOS exploratory, not virgin holdout",
                    "no freeze changes, no prospective shadow insertion, no promotion"],
      "limitations":["Constrained label permutation is not a Haar or universal graph null",
                     "Subspace overlap is geometric and not causal",
                     "Lagged rolling prefixes overlap; block bootstrap only approximately addresses dependence",
                     "Historical Blind OOS is prior-exposed and exploratory",
                     "Q60 prospective gate remains separate and requires 200 complete paired targets"]
    }
    dump(REPORT,report)
    cp=(
      "# SONAR Q96 delayed spectral recurrence — checkpoint\n\n"
      f"- Task: {TASK_ID}\n- State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE\n"
      f"- Archive: {q94.EXPECTED_DRAWS} draws, {q94.EXPECTED_FIRST} through {q94.EXPECTED_LAST}\n"
      f"- Strict-prior targets: {len(result['labels'])}; splits: {result['counts']}\n"
      f"- Fixed lags: {list(LAGS)}; requested modes: {MODES}\n"
      f"- Constrained node-label permutations: {PERM_COUNT}; seed: {PERM_SEED}\n"
      f"- Global Holm family: {len(result['holm_tests'])} lag-by-split tests\n"
      f"- Diagnostic gate: {result['primary_gate']['status']}\n\n"
      "## Interpretation boundary\n\n"
      "This is a geometric recurrence diagnostic, not a forecasting model. The target quintet is not read. Historical Blind OOS is exploratory. No promotion or freeze changes are permitted.\n\n"
      "## Next action\n\n"
      "Run independent exact replay, append-only persist all outputs, verify Git readback and replay the persisted head read-only. If no lag passes Validation and historical Blind OOS after global Holm correction, close the spectral recurrence line and prioritize Q92 acceptance plus Q60 prospective collection.\n"
    )
    CHECKPOINT.write_text(cp,encoding="utf-8")
    files={"catalog":CATALOG,"target_ledger":LEDGER,"report":REPORT,"protocol":PROTOCOL,"checkpoint":CHECKPOINT}
    manifest={"task_id":TASK_ID,"status":"COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_archive_git_blob_sha1":result["archive_sha1"],"source_archive_sha256":result["archive_sha256"],
      "accepted_q95_manifest_sha256":result["q95_manifest_sha256"],
      "accepted_q95_validation_sha256":result["q95_validation_sha256"],
      "accepted_q95_report_sha256":result["q95_report_sha256"],
      "draws":q94.EXPECTED_DRAWS,"targets":len(result["labels"]),"split_counts":result["counts"],
      "lags":list(LAGS),"permutations":PERM_COUNT,"ledger_fields":len(ledger_fields()),
      "files":{k:{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size,"sha256":sha(p)} for k,p in files.items()}}
    dump(MANIFEST,manifest)
    print(json.dumps({"task_id":TASK_ID,"status":"COMPUTED","targets":len(result["labels"]),
      "splits":result["counts"],"lags":list(LAGS),"permutations":PERM_COUNT,
      "permutation_overlap_values":len(result["labels"])*len(LAGS)*PERM_COUNT,
      "holm_tests":len(result["holm_tests"]),"primary_gate":result["primary_gate"]["status"],
      "ledger_bytes":LEDGER.stat().st_size},sort_keys=True))

def main():
    write_outputs(compute_experiment())

if __name__=="__main__":
    main()
