#!/usr/bin/env python3
"""Persist fully validated Q87 aggregate outputs with branch-head CAS and exact-byte reread."""
from __future__ import annotations
import base64, hashlib, json, os, subprocess, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BRANCH="research/per-number-condition-grammar-20261026"
OUT=ROOT/"reports/sequence_agent"
API="https://api.github.com"
def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN"); repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token: raise SystemExit("Q87_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    req=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
        "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q87-persistence"})
    try:
        with urllib.request.urlopen(req,timeout=300) as response: raw=response.read()
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode("utf-8",errors="replace")[:2000]
        raise SystemExit("Q87_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+detail) from exc
    return json.loads(raw.decode()) if raw else {}
def sha256(data): return hashlib.sha256(data).hexdigest()
def main():
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    report_path=OUT/"per_number_condition_7plus_grammar.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("task_id")!="Q87" or report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q87_PERSIST_BLOCKED: aggregate report not awaiting accepted validation")
    sys_path=str(ROOT/"scripts")
    import sys; sys.path.insert(0,sys_path)
    from sonar_research_queue import validate_q87
    errors=validate_q87()
    if errors: raise SystemExit("Q87_PERSIST_BLOCKED: acceptance validation failed: "+"; ".join(errors[:30]))
    queue=json.loads((OUT/"research_queue_status.json").read_text(encoding="utf-8"))
    task=next((x for x in queue.get("tasks",[]) if x.get("id")=="Q87"),None)
    if queue.get("queue_status")!="QUEUE_VALID" or not task or task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"):
        raise SystemExit("Q87_PERSIST_BLOCKED: queue is not validated/pending human review")
    checkpoint={
      "schema_version":"1.0","project":"VinciCasa SONAR","checkpoint_id":"SONAR-Q87-2026-10-30",
      "status":"VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION","task_id":"Q87",
      "source_checkout_head_sha":head,"source_archive_sha256":report["source_archive_sha256"],
      "target_count":report["target_count"],"last_date":report["last_date"],"formula_count":report["formula_count"],
      "metrics_rows":report["metrics_rows"],"target_ledger_rows":report["target_ledger_rows"],
      "shard_count":report["shard_count"],"global_holm_test_count":report["multiple_testing"]["test_count"],
      "metrics_manifest_sha256":json.loads((OUT/"per_number_condition_7plus_formula_metrics_manifest.json").read_text())["parts_manifest_sha256"],
      "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
      "guardrails":["no automatic promotion","no PR merge","no immutable freeze overwritten","higher-order/conditional families remain open"]
    }
    checkpoint_path=OUT/"q87_checkpoint_2026-10-30.json"
    checkpoint_path.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    paths=[str(report_path.relative_to(ROOT)),
      "reports/sequence_agent/per_number_condition_7plus_formula_metrics_manifest.json",
      "reports/sequence_agent/per_number_condition_7plus_target_ledger.csv",
      "reports/sequence_agent/research_queue_status.json",
      "reports/sequence_agent/q87_checkpoint_2026-10-30.json"]
    paths.extend(x["path"] for x in report.get("metrics_parts",[]))
    payloads={}
    for rel in paths:
        p=ROOT/rel
        if not p.is_file(): raise SystemExit("Q87_PERSIST_BLOCKED: missing output "+rel)
        payloads[rel]=p.read_bytes()
    ref=api("GET","/git/ref/heads/"+BRANCH)
    if ref.get("object",{}).get("sha")!=head: raise SystemExit("Q87_PERSIST_BLOCKED: branch head differs from exact checkout; refusing stale write")
    base_tree=api("GET","/git/commits/"+head)["tree"]["sha"]
    elements=[]; expected={}
    for rel,data in payloads.items():
        blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
        elements.append({"path":rel,"mode":"100644","type":"blob","sha":blob["sha"]})
        expected[rel]={"blob_sha":blob["sha"],"bytes":len(data),"sha256":sha256(data)}
    tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":elements})
    commit=api("POST","/git/commits",{"message":"Persist validated Q87 seven-feature formula results, global Holm family and checkpoint [q87-persisted]","tree":tree["sha"],"parents":[head]})
    if api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]!=head:
        raise SystemExit("Q87_PERSIST_BLOCKED: branch advanced during persistence; refusing ref update")
    api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
    committed=api("GET","/git/commits/"+commit["sha"])
    tree_doc=api("GET","/git/trees/"+committed["tree"]["sha"]+"?recursive=1")
    if tree_doc.get("truncated"): raise SystemExit("Q87_PERSIST_BLOCKED: persisted tree truncated")
    tree_map={x["path"]:x for x in tree_doc.get("tree",[]) if x.get("type")=="blob"}
    for rel,data in payloads.items():
        entry=tree_map.get(rel)
        if not entry or entry.get("sha")!=expected[rel]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q87_PERSIST_BLOCKED: exact-commit tree mismatch for "+rel)
        blob=api("GET","/git/blobs/"+entry["sha"]); reread=base64.b64decode(blob["content"])
        if reread!=data or sha256(reread)!=expected[rel]["sha256"]:
            raise SystemExit("Q87_PERSIST_BLOCKED: exact-byte reread mismatch for "+rel)
        print("Q87_PERSIST_VERIFIED: "+rel+" bytes="+str(len(data)))
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as h: h.write("commit_created=true\ncommit_sha="+commit["sha"]+"\n")
    print(json.dumps({"task_id":"Q87","persisted_head_sha":commit["sha"],"parent_sha":head,
      "verified_file_count":len(payloads),"verified_bytes":sum(map(len,payloads.values())),
      "all_exact_commit_bytes_verified":True,"review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
if __name__=="__main__": main()
