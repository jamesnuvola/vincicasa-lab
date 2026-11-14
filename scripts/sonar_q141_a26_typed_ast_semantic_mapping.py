#!/usr/bin/env python3
"""Q141-A26 typed-AST semantic crosswalk and Q90 operator-group ablation."""
from __future__ import annotations
import argparse,bisect,csv,gzip,hashlib,importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np

TASK="Q141-A26"; DATE="2026-11-14"
SOURCE_BRANCH="research/q141-formula-universe-behaviour-mapping-20261112"
SOURCE_COMMIT="6bc727a46c65fecceff3410a7a635e42c62b4af5"
Q7_MAP={"number_frequency":"number_occurrence","pair_interaction":"cooccurrence","triple_interaction":"cooccurrence",
"quadruple_interaction":"cooccurrence","exact_quintet_recurrence":"cooccurrence","sorted_position_frequency":"position_rank",
"gap_pattern":"gap_structure","sum_distribution":"sum_regime","odd_count":"parity","decade_profile":"decade_composition"}
Q90_MAP={"lag_2":"number_occurrence","lag_10":"number_occurrence","ewma_acceleration_7_30":"number_occurrence",
"ewma_acceleration_3_14":"number_occurrence","ewma_hit_hl_3":"number_occurrence","conditional_frequency_prev_draw_regime":"number_occurrence",
"neighbor_pm2_history":"neighbourhood","neighbor_balance_pm2_recent":"neighbourhood","neighbor_balance_pm1_recent":"neighbourhood",
"cooccurrence_surprise_recent":"cooccurrence","gap_hazard_residual":"gap_structure","gap_hazard_empirical":"gap_structure",
"gap_slope_recent":"gap_structure","rank_velocity_5_20":"position_rank","rank_consensus_27":"position_rank",
"feature_disagreement_27":"position_rank","transition_profile_affinity":"transition","regime_sum_affinity":"sum_regime",
"novelty_residual_20":"novelty","novelty_residual_50":"novelty"}
SHARED=set(Q7_MAP.values())&set(Q90_MAP.values())
CONCEPTS=("number_occurrence","cooccurrence","position_rank","gap_structure","sum_regime","parity","decade_composition","neighbourhood","transition","novelty")
CINDEX={v:i for i,v in enumerate(CONCEPTS)}
QLIN=("linear_mean_L4","linear_mean_L5","linear_mean_L6","linear_mean_L7","linear_mean_L8")
QNON=("pairwise_interaction_I4","conditional_gate_G4")
QALL=QLIN+QNON
SOURCE_PATHS=[
"reports/sequence_agent/q90_typed_ast_import_manifest_2026-11-12.json",
"reports/sequence_agent/q90_typed_ast_import_report_2026-11-12.json",
"reports/sequence_agent/q7_typed_ast_import_report_2026-11-12.json",
"reports/sequence_agent/q141_q7_ast_complexity_manifest_2026-11-12.json",
"reports/sequence_agent/q7_formula_complexity_walkforward_report_2026-11-12.json",
"reports/sequence_agent/q7_formula_complexity_walkforward_target_ledger_2026-11-12.csv",
"reports/sequence_agent/q141_formula_family_behaviour_report_2026-11-12.json",
"reports/sequence_agent/q141_formula_family_behaviour_manifest_2026-11-12.json",
"reports/sequence_agent/q141_formula_family_behaviour_target_ledger_2026-11-12.csv",
"reports/sequence_agent/q141_q90_family_persistence_report_2026-11-12.json",
"reports/sequence_agent/q141_q90_family_persistence_manifest_2026-11-12.json",
"reports/sequence_agent/q141_q90_family_persistence_target_ledger_2026-11-12.csv",
"reports/sequence_agent/q141_q90_to_q7_transfer_report_2026-11-12.json",
"scripts/sonar_q141_q90_to_q7_transfer.py","reports/sequence_agent/q7_typed_ast_catalog_part_00.jsonl.gz"]
SOURCE_PATHS += [f"reports/sequence_agent/q90_typed_ast_catalog_part_{i:02d}.jsonl.gz" for i in range(7)]
N={"report":"q141_a26_typed_ast_semantic_mapping_report_2026-11-14.json",
"md":"q141_a26_typed_ast_semantic_mapping_report_2026-11-14.md","crosswalk":"q141_a26_semantic_crosswalk_2026-11-14.csv",
"ledger":"q141_a26_operator_ablation_target_ledger_2026-11-14.csv","semantic":"q141_a26_semantic_signature_summary_2026-11-14.json",
"validation":"q141_a26_validation_2026-11-14.json","manifest":"q141_a26_manifest_2026-11-14.json",
"checkpoint":"q141_a26_checkpoint_2026-11-14.json","receipt":"q141_a26_readback_receipt_2026-11-14.json"}
TOL=1e-10; PRACTICAL=.005; SEED=14120261114

def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def rjson(p): return json.loads(p.read_text(encoding="utf-8"))
def wjson(p,v): p.write_text(json.dumps(v,sort_keys=True,indent=2)+"\n",encoding="utf-8")
def rcsv(p):
 with p.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def wcsv(p,rows,cols):
 with p.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows)

def load_c5(root):
 spec=importlib.util.spec_from_file_location("q141_c5_pinned",root/"scripts/sonar_q141_q90_to_q7_transfer.py")
 if spec is None or spec.loader is None:raise RuntimeError("cannot load pinned C5 runner")
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def verify_ast_meta(root):
 b=root/"reports/sequence_agent"
 fixed={
 "q90_typed_ast_import_manifest_2026-11-12.json":("f1543a7e27d290c683386ec08a6a3adb9d2ff77a","fa2f6441634d878db1885d04cd2da23bc4761d14e3531f27c28c9ec8323865cd"),
 "q90_typed_ast_import_report_2026-11-12.json":("5c33823615852eac3a7821dca2851e54347599e5","d570fea75535d90ec52de4abca07ec531a33d46c3be2c273b6be21946d42e0c9"),
 "q7_typed_ast_import_report_2026-11-12.json":("5dbb328ad58f46a7a993f1416f90dff3fb98e917","4fd709840b5ee752f233451e3d1f584827aae33e307b91176523182f436d65ef"),
 "q141_q7_ast_complexity_manifest_2026-11-12.json":("acd4bd6f42458626e422718c6f80a65a5aa76eb5","1729de7e4bf8e83db8bcb13c8d3e4668351694769bb6b6ec41d1fa2ed4365de3")}
 for name,(gb,hs) in fixed.items():
  data=(b/name).read_bytes()
  if blob(data)!=gb or sha(data)!=hs:raise RuntimeError("AST metadata hash mismatch: "+name)
 qm=rjson(b/"q90_typed_ast_import_manifest_2026-11-12.json")
 qr=rjson(b/"q90_typed_ast_import_report_2026-11-12.json")
 q7r=rjson(b/"q7_typed_ast_import_report_2026-11-12.json")
 q7m=rjson(b/"q141_q7_ast_complexity_manifest_2026-11-12.json")
 if qm.get("formula_total")!=330429 or qm.get("unique_ast_count")!=330429 or qm.get("duplicate_ast_count")!=0:raise RuntimeError("Q90 AST totals mismatch")
 if qm.get("formula_type_counts")!={"linear_mean":262599,"pairwise_interaction":29070,"conditional_gate":38760}:raise RuntimeError("Q90 operator counts mismatch")
 if q7r.get("formula_count")!=1023 or q7r.get("unique_canonical_ast_ids")!=1023 or q7r.get("output_type")!="quintet_score":raise RuntimeError("Q7 AST totals/output mismatch")
 if set(qr["feature_universe"]["selected_feature_names"])!=set(Q90_MAP):raise RuntimeError("Q90 feature map mismatch")
 if {x["name"] for x in q7r["feature_families"]}!=set(Q7_MAP):raise RuntimeError("Q7 family map mismatch")
 if qm.get("q90_archive_git_blob_sha1")!="5d2efd70684e918b27d8f06386d545647898336d":raise RuntimeError("Q90 archive lineage mismatch")
 if q7r.get("source_archive_blob_sha1")!="7dab05ba49ace909fe8783eef729605049c65e50":raise RuntimeError("Q7 archive lineage mismatch")
 return qm,q7m

def refs(node):
 out=set()
 def walk(v):
  if isinstance(v,dict):
   if v.get("op")=="feature_ref" and v.get("namespace")=="Q89":out.add(str(v.get("name","")))
   if v.get("namespace")=="Q7" and "feature_id" in v:out.add(str(v["feature_id"]))
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(node);return {x for x in out if x}

def op_type(ast):
 t=ast.get("term",{})
 if t.get("op")=="mean":return "linear_mean"
 if t.get("op")=="add":
  for x in t.get("terms",[]):
   if x.get("op")=="scale":
    inner=x.get("term",{})
    if inner.get("op")=="candidate_zscore":return "pairwise_interaction"
    if inner.get("op")=="indicator":return "conditional_gate"
 raise RuntimeError("unknown Q90 AST operator")

def mask(names,mapping):
 m=0
 for x in names:m|=1<<CINDEX[mapping[x]]
 return m

def audit_asts(root,qm,q7m):
 b=root/"reports/sequence_agent";q90ids=set();q90fids=set();q90raw=set();q90masks=Counter();q90ops=Counter();q90features=Counter();q90shared=0
 for shard in qm["shards"]:
  p=b/shard["path"];data=p.read_bytes()
  if len(data)!=shard["bytes"] or sha(data)!=shard["sha256"] or blob(data)!=shard["git_blob_sha1"]:raise RuntimeError("Q90 AST shard hash mismatch")
  n=0
  with gzip.open(p,"rt",encoding="utf-8") as f:
   for line in f:
    if not line.strip():continue
    rec=json.loads(line);ast=rec["canonical_ast"]
    if rec.get("output_type")!="per_number_score":raise RuntimeError("Q90 output type mismatch")
    raw=sha(canon(ast))
    if rec.get("ast_id")!="Q90AST1-"+raw:raise RuntimeError("Q90 AST hash mismatch")
    if rec["ast_id"] in q90ids or rec["source_formula_id"] in q90fids:raise RuntimeError("duplicate Q90 AST/formula")
    q90ids.add(rec["ast_id"]);q90fids.add(rec["source_formula_id"]);q90raw.add(raw)
    names=refs(ast)
    if not names or not names.issubset(Q90_MAP):raise RuntimeError("unmapped Q90 feature ref")
    q90ops[op_type(ast)]+=1;q90masks[mask(names,Q90_MAP)]+=1;q90features.update(names)
    if any(Q90_MAP[x] in SHARED for x in names):q90shared+=1
    n+=1
  if n!=shard["rows"]:raise RuntimeError("Q90 shard row count mismatch")
 p=b/"q7_typed_ast_catalog_part_00.jsonl.gz";meta=q7m["files"]["q7_typed_ast_catalog_part_00.jsonl.gz"];data=p.read_bytes()
 if len(data)!=meta["bytes"] or sha(data)!=meta["sha256"] or blob(data)!=meta["git_blob_sha1"]:raise RuntimeError("Q7 AST shard hash mismatch")
 q7ids=set();q7fids=set();q7raw=set();q7masks=Counter();q7features=Counter();q7shared=0
 with gzip.open(p,"rt",encoding="utf-8") as f:
  for line in f:
   if not line.strip():continue
   rec=json.loads(line);ast=rec["canonical_ast"]
   if rec.get("output_type")!="quintet_score":raise RuntimeError("Q7 output type mismatch")
   raw=sha(canon(ast))
   if rec.get("ast_id")!="Q7AST1-"+raw:raise RuntimeError("Q7 AST hash mismatch")
   if rec["ast_id"] in q7ids or rec["source_formula_id"] in q7fids:raise RuntimeError("duplicate Q7 AST/formula")
   q7ids.add(rec["ast_id"]);q7fids.add(rec["source_formula_id"]);q7raw.add(raw)
   names=refs(ast)
   if not names or not names.issubset(Q7_MAP):raise RuntimeError("unmapped Q7 family ref")
   q7masks[mask(names,Q7_MAP)]+=1;q7features.update(names)
   if any(Q7_MAP[x] in SHARED for x in names):q7shared+=1
 if len(q90ids)!=330429 or len(q7ids)!=1023:raise RuntimeError("AST catalog total mismatch")
 if q90ops!=Counter({"linear_mean":262599,"pairwise_interaction":29070,"conditional_gate":38760}):raise RuntimeError("Q90 operator family mismatch")
 cross=len(q90raw&q7raw)
 if cross:raise RuntimeError("raw AST equality across incompatible output types; stop for review")
 q7set=set(q7masks);best=[];coarse=0
 for m,n in q90masks.items():
  v=max((m&o).bit_count()/(m|o).bit_count() for o in q7set);best.extend([v]*n)
  if m in q7set:coarse+=n
 a=np.asarray(best)
 return {"q90_formula_count":len(q90ids),"q90_unique_ast_ids":len(q90ids),"q90_duplicate_ast_count":330429-len(q90ids),
 "q90_operator_counts":dict(q90ops),"q90_feature_reference_counts":dict(q90features),"q90_unique_coarse_signatures":len(q90masks),
 "q90_formulas_with_shared_concept":q90shared,"q90_shared_concept_formula_fraction":q90shared/330429,
 "q7_formula_count":len(q7ids),"q7_unique_ast_ids":len(q7ids),"q7_duplicate_ast_count":1023-len(q7ids),
 "q7_feature_reference_counts":dict(q7features),"q7_unique_coarse_signatures":len(q7masks),"q7_formulas_with_shared_concept":q7shared,
 "q7_shared_concept_formula_fraction":q7shared/1023,"shared_concepts":sorted(SHARED),
 "q90_only_concepts":sorted(set(Q90_MAP.values())-set(Q7_MAP.values())),
 "q7_only_concepts":sorted(set(Q7_MAP.values())-set(Q90_MAP.values())),
 "q90_feature_shared_coverage":sum(v in SHARED for v in Q90_MAP.values())/20,
 "q7_family_shared_coverage":sum(v in SHARED for v in Q7_MAP.values())/10,
 "q90_formulas_with_coarse_signature_match":coarse,
 "q90_best_jaccard_to_q7_signature":{"mean":float(a.mean()),"median":float(np.median(a)),"p90":float(np.quantile(a,.9))},
 "cross_output_raw_ast_matches":cross,"cross_output_exact_equivalence_allowed":False,
 "interpretation":"Coarse concept signatures are ontology-level relatedness only, not mathematical/function equivalence; per_number_score and quintet_score remain separate."}

def strict_prior_window(rows,keys,target,window,key):
 idx=bisect.bisect_left(keys,target);prior=rows[max(0,idx-window):idx]
 if len(prior)!=window or [int(r[key]) for r in prior]!=list(range(target-window,target)):raise RuntimeError("strict-prior window gap/current/future")
 return prior

def group_state(rows,columns):
 x=np.asarray([[float(r[c]) for c in columns] for r in rows])
 if not np.isfinite(x).all() or np.any(x<0) or np.any(x>1):raise RuntimeError("Q90 subgroup values outside [0,1]")
 means=x.mean(axis=0);total=float(means.sum())
 if total<=0:ent=0.0
 else:
  p=means/total;ent=float(-np.sum(p[p>0]*np.log(p[p>0]))/math.log(len(columns)))
 eq=x.mean(axis=1)
 return [float(eq.mean()),float(means.std()),ent,float(eq[-25:].mean()-eq[:25].mean())]

def holm(p):
 order=sorted(range(len(p)),key=lambda i:p[i]);out=[1.0]*len(p);running=0.0
 for rank,i in enumerate(order):running=max(running,min(1.0,(len(p)-rank)*p[i]));out[i]=running
 return out

def ablation(root,c5):
 q7=c5.read_csv(c5.Q7_LEDGER);q80=c5.read_csv(c5.Q80_LEDGER);q90=c5.read_csv(c5.Q90_LEDGER)
 c5.validate_and_join(q7,q80,q90)
 x0,xbase,xall,feature_rows=c5.build_features(q7,q80,q90)
 n=len(q7);xlin=np.full((n,xbase.shape[1]+4),np.nan);xnon=np.full_like(xlin,np.nan)
 xlin[:,:xbase.shape[1]]=xbase;xnon[:,:xbase.shape[1]]=xbase
 keys=[int(r["prior_draws"]) for r in q90]
 for i in range(c5.WINDOW,n):
  ix=int(q7[i]["prior_draws"]);prior=strict_prior_window(q90,keys,ix,c5.WINDOW,"prior_draws")
  if any(r["target_date"]>q7[i]["cutoff_date"] for r in prior):raise RuntimeError("Q90 predictor after target cutoff")
  xlin[i,xbase.shape[1]:]=group_state(prior,QLIN);xnon[i,xbase.shape[1]:]=group_state(prior,QNON)
 matrices={"m0_q7_q80":xbase,"m1_linear":xlin,"m2_nonlinear":xnon,"m3_all_q90":xall}
 y=np.asarray([float(r["mean_percentile_all_formulas"]) for r in q7]);pred={k:np.full(n,np.nan) for k in matrices}
 for i in range(100,c5.DISCOVERY_END):
  tr=np.arange(c5.WINDOW,i)
  for name,m in matrices.items():pred[name][i]=float(c5.predict_ridge(c5.fit_ridge(m[tr],y[tr]),m[i:i+1])[0])
 tr=np.arange(c5.WINDOW,c5.DISCOVERY_END);frozen={k:c5.fit_ridge(m[tr],y[tr]) for k,m in matrices.items()}
 for i in range(c5.DISCOVERY_END,n):
  for k,m in matrices.items():pred[k][i]=float(c5.predict_ridge(frozen[k],m[i:i+1])[0])
 if any(not np.isfinite(v[100:]).all() for v in pred.values()):raise RuntimeError("non-finite A26 prediction")
 slices={"discovery":(100,c5.DISCOVERY_END),"validation":(c5.DISCOVERY_END,c5.VALIDATION_END),"blind_oos":(c5.VALIDATION_END,n)}
 metrics={}
 for split,(s,e) in slices.items():
  base=c5.metric_summary(y[s:e],pred["m0_q7_q80"][s:e]);mods={}
  for k in ("m1_linear","m2_nonlinear","m3_all_q90"):
   cur=c5.metric_summary(y[s:e],pred[k][s:e]);mods[k]={**cur,"mae_gain_vs_m0":base["mae"]-cur["mae"],"rmse_gain_vs_m0":base["rmse"]-cur["rmse"]}
  metrics[split]={"targets":e-s,"m0_q7_q80_baseline":base,"models":mods}
 c5r=c5.read_json(c5.REPORT)["metrics_by_split"];parity=[]
 for split in slices:
  for model,key in (("m0_q7_q80_baseline","m1_q7_q80_ridge"),("m3_all_q90","m2_q7_q80_q90_ridge")):
   actual=metrics[split]["m0_q7_q80_baseline"] if model=="m0_q7_q80_baseline" else metrics[split]["models"][model]
   expected=c5r[split][key]
   for metric in ("mae","rmse","mean_prediction_error","pearson_correlation"):
    a=actual[metric];b=expected[metric]
    if a is None or b is None:
     if a is not b:raise RuntimeError("C5 parity null mismatch")
    elif abs(float(a)-float(b))>TOL:raise RuntimeError(f"C5 replay parity mismatch {split}/{model}/{metric}")
    parity.append(0.0 if a is None else abs(float(a)-float(b)))
 s,e=slices["blind_oos"];baseabs=np.abs(pred["m0_q7_q80"][s:e]-y[s:e]);primary=[]
 for j,k in enumerate(("m1_linear","m2_nonlinear")):
  effect=baseabs-np.abs(pred[k][s:e]-y[s:e])
  p=c5.block_signflip_p(effect,c5.BLOCK_LENGTH,c5.REPLICATES,SEED+j)
  ci=c5.moving_block_ci(effect,c5.BLOCK_LENGTH,c5.REPLICATES,SEED+10+j)
  primary.append({"model":k,"targets":len(effect),"mae_gain":float(effect.mean()),"ci95_moving_block":ci,"p_raw":p})
 adj=holm([x["p_raw"] for x in primary])
 for item,p in zip(primary,adj):
  item["p_holm_two_tests"]=p;item["passes_practical"]=item["mae_gain"]>=PRACTICAL
  item["passes_statistical"]=p<.05 and item["ci95_moving_block"][0]>0
  item["passes_full_gate"]=item["passes_practical"] and item["passes_statistical"]
 effect3=baseabs-np.abs(pred["m3_all_q90"][s:e]-y[s:e])
 m3={"mae_gain_vs_m0":float(effect3.mean()),"ci95_moving_block_descriptive":c5.moving_block_ci(effect3,c5.BLOCK_LENGTH,c5.REPLICATES,SEED+20)}
 ledger=[]
 for i,row in enumerate(q7):
  rec={"target_index":int(row["prior_draws"]),"target_date":row["target_date"],"cutoff_date":row["cutoff_date"],
   "actual_quintet":row["actual_quintet"],"split":row["split"],"target_mean_percentile":float(y[i]),
   "prediction_available":i>=100,"prediction_mode":"warmup" if i<100 else ("expanding_prequential_discovery" if i<c5.DISCOVERY_END else "frozen_discovery_coefficients")}
  for name,m in matrices.items():
   rec[name+"_prediction"]="" if i<100 else float(pred[name][i])
   rec[name+"_absolute_error"]="" if i<100 else abs(float(pred[name][i])-float(y[i]))
  ledger.append(rec)
 return {"decision":"SEMANTIC_OPERATOR_SUBGROUP_INCREMENTAL_LIFT_DEMONSTRATED_EXPLORATORY" if any(x["passes_full_gate"] for x in primary) else "NO_SEMANTIC_OPERATOR_SUBGROUP_INCREMENTAL_LIFT_DEMONSTRATED",
 "metrics_by_split":metrics,"primary_blind_tests":primary,"m3_full_q90_reproduction_control":m3,
 "c5_replay_parity":{"checks":len(parity),"max_absolute_error":max(parity),"passed":True},
 "walkforward":{"source_rows":n,"forecast_rows":sum(v["targets"] for v in metrics.values()),"warmup_rows":100,"feature_window":c5.WINDOW,
 "split_source_rows":{"discovery":1972,"validation":657,"blind_oos":657},"split_forecasts":{"discovery":1872,"validation":657,"blind_oos":657},
 "strict_prior":True,"discovery_expanding_prequential":True,"validation_blind_coefficients_frozen":True,"ridge_alpha":c5.RIDGE_ALPHA},
 "ledger":ledger}

def source_lineage(root):
 files=[]
 for rel in SOURCE_PATHS:
  data=(root/rel).read_bytes();files.append({"path":rel,"bytes":len(data),"git_blob_sha1":blob(data),"sha256":sha(data)})
 return {"branch":SOURCE_BRANCH,"commit":SOURCE_COMMIT,"files":files}

def crosswalk():
 rows=[]
 for ns,mapping,other,outtype in (("Q7",Q7_MAP,Q90_MAP,"quintet_score"),("Q90",Q90_MAP,Q7_MAP,"per_number_score")):
  for name,concept in mapping.items():
   matches=sorted(k for k,v in other.items() if v==concept)
   rows.append({"source_namespace":ns,"source_feature":name,"semantic_concept":concept,"related_features_other_source":";".join(matches),
   "relation":"RELATED_NOT_EQUIVALENT" if matches else "SOURCE_SPECIFIC_NO_MATCH","exact_equivalence":"false","output_type":outtype})
 return rows

def markdown(r,s,v):
 lines=["# Q141-A26 — Typed-AST semantic mapping and operator-group transfer ablation","",
 "Status: "+r["status"],"Decision: "+r["decision"],"","## Structural semantic audit",
 f"Q90: {s['q90_formula_count']:,} typed ASTs; Q7: {s['q7_formula_count']:,}.",
 "Shared concepts: "+", ".join(s["shared_concepts"])+".",
 "Q90-only: "+", ".join(s["q90_only_concepts"])+". Q7-only: "+", ".join(s["q7_only_concepts"])+".",
 f"Shared concept coverage: Q90 features {s['q90_feature_shared_coverage']:.1%}; Q7 families {s['q7_family_shared_coverage']:.1%}.",
 "No cross-output raw AST equality; exact cross-type equivalence is prohibited. Coarse signatures are relatedness, not functional identity.","",
 "| Split | n | Q7+Q80 baseline MAE | Linear-only MAE | Nonlinear-only MAE | All-Q90 MAE |","|---|---:|---:|---:|---:|---:|"]
 for split in ("discovery","validation","blind_oos"):
  m=r["metrics_by_split"][split]
  lines.append(f"| {split} | {m['targets']} | {m['m0_q7_q80_baseline']['mae']:.6f} | {m['models']['m1_linear']['mae']:.6f} | {m['models']['m2_nonlinear']['mae']:.6f} | {m['models']['m3_all_q90']['mae']:.6f} |")
 lines+=["","## Blind OOS primary tests","",
 "| Model | MAE gain | 95% block CI | p raw | p Holm | Gate |","|---|---:|---:|---:|---:|---|"]
 for x in r["primary_blind_tests"]:
  lines.append(f"| {x['model']} | {x['mae_gain']:+.6f} | [{x['ci95_moving_block'][0]:+.6f}, {x['ci95_moving_block'][1]:+.6f}] | {x['p_raw']:.6f} | {x['p_holm_two_tests']:.6f} | {'PASS' if x['passes_full_gate'] else 'FAIL'} |")
 lines+=["",f"Full-Q90 reproduction-control gain: {r['m3_full_q90_reproduction_control']['mae_gain_vs_m0']:+.6f}.",
 f"C5 parity: {r['c5_replay_parity']['checks']} metrics; max absolute error {r['c5_replay_parity']['max_absolute_error']:.3e}.",
 "","## Limits","",
 f"{r['walkforward']['forecast_rows']:,} strict-prior forecasts; 100 warm-up rows; 50-target feature window.",
 "Discovery is expanding-prequential; Validation and Blind coefficients are frozen after Discovery.",
 "Q90 has 330,429 ASTs, but the behaviour ledger is a fixed 700-formula sample. Q90 selected 20 of 59 features.",
 "Q7 and Q90 cutoffs differ; only 3,286 exact aligned targets are used. Historical Blind OOS is exposed and this decomposition is exploratory.",
 "Endpoint is Q7 formula-universe rank quality, not winning-number or exact-ticket prediction. Holm covers two A26 tests only.",
 "","Replay verified: "+str(v.get("replay_verified",False))+".","",
 "Next: rebuild Q90 and Q7 from one identical current canonical archive and collect genuinely prospective common-source targets; do not tune on this exposed Blind OOS.",""]
 return "\n".join(lines)

def write_manifest(out,source,status):
 files=[]
 for key in ("report","md","crosswalk","ledger","semantic","validation"):
  p=out/N[key];data=p.read_bytes();files.append({"path":"reports/sequence_agent/"+N[key],"bytes":len(data),"sha256":sha(data),"git_blob_sha1":blob(data),"label":key})
 repo=Path(__file__).resolve().parents[1];code=[]
 for rel in ("scripts/sonar_q141_a26_typed_ast_semantic_mapping.py","tests/test_sonar_q141_a26_typed_ast_semantic_mapping.py",
 ".github/workflows/q141-a26-typed-ast-semantic-mapping.yml","reports/sequence_agent/q141_a26_typed_ast_semantic_mapping_preregistration_2026-11-14.json",
 "reports/sequence_agent/q141_a26_typed_ast_semantic_mapping_preregistration_2026-11-14.md"):
  data=(repo/rel).read_bytes();code.append({"path":rel,"bytes":len(data),"sha256":sha(data),"git_blob_sha1":blob(data)})
 wjson(out/N["manifest"],{"schema_version":"1.0","task_id":TASK,"status":status,"source":source,"files":files,"code_lineage":code,
 "multiplicity":"Holm across two primary subgroup endpoints only; no global Q00-Q141 correction.",
 "research_status":"post_hoc_decomposition_of_exposed_historical_blind_oos"})

def main():
 p=argparse.ArgumentParser();p.add_argument("--source-root",type=Path);p.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parents[1]/"reports/sequence_agent")
 p.add_argument("--finalize-replay",action="store_true");a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
 if a.finalize_replay:
  r=rjson(out/N["report"]);v=rjson(out/N["validation"]);v["replay_verified"]=True;v["status"]="COMPUTED_REPLAY_VERIFIED";r["status"]="COMPUTED_REPLAY_VERIFIED"
  wjson(out/N["report"],r);wjson(out/N["validation"],v);s=rjson(out/N["semantic"]);(out/N["md"]).write_text(markdown(r,s,v),encoding="utf-8")
  m=rjson(out/N["manifest"]);write_manifest(out,m["source"],"COMPUTED_REPLAY_VERIFIED")
  cp=rjson(out/N["checkpoint"]);cp["status"]="COMPUTED_REPLAY_VERIFIED";cp["manifest_sha256"]=sha((out/N["manifest"]).read_bytes());wjson(out/N["checkpoint"],cp);return
 if a.source_root is None:raise SystemExit("--source-root required")
 root=a.source_root.resolve();c5=load_c5(root);c5.verify_sources()
 qm,q7m=verify_ast_meta(root);semantic=audit_asts(root,qm,q7m);walk=ablation(root,c5);source=source_lineage(root)
 report={"schema_version":"1.0","task_id":TASK,"date":DATE,"status":"COMPUTED_REPLAY_PENDING","decision":walk["decision"],
 "hypothesis":"At least one Q90 AST operator subgroup improves Q7+Q80 baseline by at least 0.005 MAE in exposed historical Blind OOS, with positive block CI and Holm p<0.05.",
 "estimand":"Next-target mean percentile over 1,023 Q7 quintet_score formulas; not winning-number or ticket prediction.",
 "semantic_audit":semantic,"semantic_mapping":{"q7_family_to_concept":Q7_MAP,"q90_feature_to_concept":Q90_MAP,"shared_concepts":sorted(SHARED),"relation":"RELATED_NOT_EQUIVALENT"},
 "walkforward":walk["walkforward"],"metrics_by_split":walk["metrics_by_split"],"primary_blind_tests":walk["primary_blind_tests"],
 "m3_full_q90_reproduction_control":walk["m3_full_q90_reproduction_control"],"c5_replay_parity":walk["c5_replay_parity"],
 "source":{**source,"q7_archive_git_blob_sha1":"7dab05ba49ace909fe8783eef729605049c65e50","q90_archive_git_blob_sha1":"5d2efd70684e918b27d8f06386d545647898336d",
 "q141_archive_git_blob_sha1":"fcb453ed06c8002314f826dbac79d6935f9ac103","q90_artifact_sha256":"12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077",
 "q7_cutoff":"2026-10-24","q90_cutoff":"2026-11-07","q90_full_ast_count":330429,"q90_behaviour_sample_count":700,"q7_ast_count":1023,"aligned_targets":3286},
 "multiplicity":{"primary_tests":2,"method":"Holm-Bonferroni","block_length":20,"replicates":20000,"seed":SEED,"global_q00_q141_correction":"not covered"},
 "limitations":["Historical Blind OOS was exposed; exploratory only.","Q90 behaviour ledger is a fixed 700-formula sample, not all 330,429 ASTs.",
 "Q90 selected 20 of 59 features.","Q7/Q90 cutoffs differ; only 3,286 aligned targets are used.","per_number_score and quintet_score are different output types; semantic links are not equivalences.",
 "Endpoint is Q7 formula-universe rank quality, not winning-number accuracy.","Holm covers two A26 endpoints only."],
 "governance":{"research_only":True,"no_merge":True,"no_engine_promotion":True,"no_archive_mutation":True,"no_shadow_insertion":True,"protected_prs_untouched":[6,7,8]}}
 validation={"schema_version":"1.0","task_id":TASK,"status":"COMPUTED_REPLAY_PENDING","ast_audit":semantic,"walkforward":walk["walkforward"],
 "strict_prior_join_rows":3286,"forecast_rows":walk["walkforward"]["forecast_rows"],"cutoff_before_target_verified":True,
 "current_future_predictors_excluded":True,"discovery_expanding_prequential":True,"validation_blind_coefficients_frozen":True,
 "c5_replay_parity":walk["c5_replay_parity"],"replay_verified":False,"focused_test_contract":"17 unit tests run before analysis by workflow","source_commit":SOURCE_COMMIT}
 wjson(out/N["report"],report);wjson(out/N["semantic"],semantic);wjson(out/N["validation"],validation)
 (out/N["md"]).write_text(markdown(report,semantic,validation),encoding="utf-8")
 rows=crosswalk();wcsv(out/N["crosswalk"],rows,["source_namespace","source_feature","semantic_concept","related_features_other_source","relation","exact_equivalence","output_type"])
 ledger=walk["ledger"];wcsv(out/N["ledger"],ledger,list(ledger[0].keys()))
 write_manifest(out,source,"COMPUTED_REPLAY_PENDING")
 wjson(out/N["checkpoint"],{"schema_version":"1.0","task_id":TASK,"status":"COMPUTED_REPLAY_PENDING","branch":"research/q141-a26-typed-ast-semantic-mapping-20261114",
 "source_commit":SOURCE_COMMIT,"manifest_path":N["manifest"],"manifest_sha256":sha((out/N["manifest"]).read_bytes()),
 "next_action":"Rebuild Q90 and Q7 from one identical current canonical archive and collect prospective common-source targets; do not tune on exposed historical Blind OOS.",
 "governance":{"no_merge":True,"no_promotion":True,"protected_prs_untouched":[6,7,8]}})

if __name__=="__main__":main()
