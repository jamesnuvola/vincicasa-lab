#!/usr/bin/env python3
"""Persist fully validated Q89 aggregate outputs with branch-head CAS and exact-byte reread."""
from __future__ import annotations
import base64, hashlib, http.client, json, os, subprocess, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BRANCH="research/per-number-condition-q89-nine-feature-20261109"
OUT=ROOT/"reports/sequence_agent"
API="https://api.github.com"
def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN"); repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token: raise SystemExit("Q89_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    for attempt in range(7):
        req=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
            "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
            "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q89-persistence"})
        try:
            with urllib.request.urlopen(req,timeout=300) as response: raw=response.read()
            return json.loads(raw.decode()) if raw else {}
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")[:2000]
            retryable=exc.code in (429,500,502,503,504) or (exc.code==403 and ("rate limit" in detail.lower() or exc.headers.get("X-RateLimit-Remaining")=="0"))
            if retryable and attempt<6:
                retry_after=exc.headers.get("Retry-After")
                try: delay=float(retry_after) if retry_after else min(2**attempt,60)
                except (TypeError,ValueError): delay=min(2**attempt,60)
                reset=exc.headers.get("X-RateLimit-Reset")
                if exc.code==403 and reset:
                    try: delay=max(delay,min(max(0,float(reset)-time.time()),60))
                    except (TypeError,ValueError): pass
                delay=max(1,min(delay,60))
                print("Q89_PERSIST_RETRY: HTTP "+str(exc.code)+" attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s")
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+detail) from exc
        except (http.client.IncompleteRead, http.client.RemoteDisconnected, ConnectionError, TimeoutError) as exc:
            if attempt<6:
                delay=min(2**attempt,60)
                print("Q89_PERSIST_RETRY: incomplete response attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s error="+repr(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: incomplete response after retries "+repr(exc)) from exc
        except urllib.error.URLError as exc:
            if attempt<6:
                delay=min(2**attempt,60)
                print("Q89_PERSIST_RETRY: network attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s error="+str(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: network error "+str(exc)) from exc
    raise SystemExit("Q89_PERSIST_BLOCKED: API retry budget exhausted")
def sha256(data): return hashlib.sha256(data).hexdigest()
def main():
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    report_path=OUT/"per_number_condition_9plus_grammar.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("task_id")!="Q89" or report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q89_PERSIST_BLOCKED: aggregate report not awaiting accepted validation")
    sys_path=str(ROOT/"scripts")
    import sys; sys.path.insert(0,sys_path)
    from sonar_research_queue import validate_q89
    errors=validate_q89()
    if errors: raise SystemExit("Q89_PERSIST_BLOCKED: acceptance validation failed: "+"; ".join(errors[:30]))
    # Promote only the technical evidence status after the fail-closed validator passes.
    report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    errors=validate_q89()
    if errors: raise SystemExit("Q89_PERSIST_BLOCKED: post-status acceptance validation failed: "+"; ".join(errors[:30]))
    # Refresh the queue after Q89 acceptance status is set; the previous snapshot
    # was generated before this report became validator-clean.
    subprocess.run(["python", str(ROOT/"scripts/sonar_research_queue.py")], cwd=ROOT, check=True)
    queue=json.loads((OUT/"research_queue_status.json").read_text(encoding="utf-8"))
    task=next((x for x in queue.get("tasks",[]) if x.get("id")=="Q89"),None)
    if queue.get("queue_status")!="QUEUE_VALID" or not task or task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"):
        raise SystemExit("Q89_PERSIST_BLOCKED: queue is not validated/pending human review")
    run_id=os.environ.get("GITHUB_RUN_ID","unknown")
    archive_cutoff=report["last_date"]
    checkpoint={
      "schema_version":"1.0","project":"VinciCasa SONAR",
      "checkpoint_id":"SONAR-Q89-"+archive_cutoff+"-RUN-"+run_id,
      "status":"VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION","task_id":"Q89",
      "workflow_run_id":run_id,"created_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_checkout_head_sha":head,"source_archive_sha256":report["source_archive_sha256"],
      "target_count":report["target_count"],"scored_targets":report["scored_targets"],
      "first_date":report["first_date"],"last_date":archive_cutoff,"formula_count":report["formula_count"],
      "metrics_rows":report["metrics_rows"],"target_ledger_rows":report["target_ledger_rows"],
      "shard_count":report["shard_count"],"global_holm_test_count":report["multiple_testing"]["test_count"],
      "metrics_manifest_sha256":json.loads((OUT/"per_number_condition_9plus_formula_metrics_manifest.json").read_text())["parts_manifest_sha256"],
      "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
      "guardrails":["no automatic promotion","no PR merge","no immutable freeze overwritten","higher-order/conditional families remain open"]
    }
    checkpoint_path=OUT/f"q89_checkpoint_{archive_cutoff}_run_{run_id}.json"
    checkpoint_path.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    paths=[str(report_path.relative_to(ROOT)),
      "reports/sequence_agent/per_number_condition_9plus_formula_metrics_manifest.json",
      "reports/sequence_agent/per_number_condition_9plus_target_ledger.csv",
      "reports/sequence_agent/research_queue_status.json",
      str(checkpoint_path.relative_to(ROOT))]
    paths.extend(x["path"] for x in report.get("metrics_parts",[]))
    payloads={}
    for rel in paths:
        p=ROOT/rel
        if not p.is_file(): raise SystemExit("Q89_PERSIST_BLOCKED: missing output "+rel)
        payloads[rel]=p.read_bytes()
    ref=api("GET","/git/ref/heads/"+BRANCH)
    if ref.get("object",{}).get("sha")!=head: raise SystemExit("Q89_PERSIST_BLOCKED: branch head differs from exact checkout; refusing stale write")
    base_tree=api("GET","/git/commits/"+head)["tree"]["sha"]
    elements=[]; expected={}
    for rel,data in payloads.items():
        blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
        elements.append({"path":rel,"mode":"100644","type":"blob","sha":blob["sha"]})
        expected[rel]={"blob_sha":blob["sha"],"bytes":len(data),"sha256":sha256(data)}
    tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":elements})
    commit=api("POST","/git/commits",{"message":"Persist validated Q89 nine-feature outputs [q89-persisted]","tree":tree["sha"],"parents":[head]})
    if api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]!=head:
        raise SystemExit("Q89_PERSIST_BLOCKED: branch advanced during persistence; refusing ref update")
    try:
        api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
    except SystemExit:
        current_ref=api("GET","/git/ref/heads/"+BRANCH)
        if current_ref.get("object",{}).get("sha")!=commit["sha"]: raise
        print("Q89_PERSIST_REF_UPDATE_VERIFIED_AFTER_TRANSIENT_RESPONSE")
    committed=api("GET","/git/commits/"+commit["sha"])
    tree_doc=api("GET","/git/trees/"+committed["tree"]["sha"]+"?recursive=1")
    if tree_doc.get("truncated"): raise SystemExit("Q89_PERSIST_BLOCKED: persisted tree truncated")
    tree_map={x["path"]:x for x in tree_doc.get("tree",[]) if x.get("type")=="blob"}
    for rel,data in payloads.items():
        entry=tree_map.get(rel)
        if not entry or entry.get("sha")!=expected[rel]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q89_PERSIST_BLOCKED: exact-commit tree mismatch for "+rel)
        blob=api("GET","/git/blobs/"+entry["sha"]); reread=base64.b64decode(blob["content"])
        if reread!=data or sha256(reread)!=expected[rel]["sha256"]:
            raise SystemExit("Q89_PERSIST_BLOCKED: exact-byte reread mismatch for "+rel)
        print("Q89_PERSIST_VERIFIED: "+rel+" bytes="+str(len(data)))
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as h: h.write("commit_created=true\ncommit_sha="+commit["sha"]+"\n")
    print(json.dumps({"task_id":"Q89","persisted_head_sha":commit["sha"],"parent_sha":head,
      "verified_file_count":len(payloads),"verified_bytes":sum(map(len,payloads.values())),
      "all_exact_commit_bytes_verified":True,"review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
if __name__=="__main__": main()
