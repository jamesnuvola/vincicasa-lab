#!/usr/bin/env python3
"""Persist fully validated Q89 aggregate outputs with branch-head CAS and exact-byte reread."""
from __future__ import annotations
import base64, hashlib, http.client, json, os, subprocess, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BRANCH="research/per-number-condition-q89-nine-feature-20261109"
OUT=ROOT/"reports/sequence_agent"
MUTABLE_OUTPUT_PATHS={"reports/sequence_agent/research_queue_status.json"}
API="https://api.github.com"
def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN"); repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token: raise SystemExit("Q89_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    for attempt in range(10):
        req=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
            "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
            "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q89-persistence"})
        try:
            with urllib.request.urlopen(req,timeout=300) as response: raw=response.read()
            if method in ("POST","PATCH"): time.sleep(0.05)
            return json.loads(raw.decode()) if raw else {}
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")[:2000]
            retryable=exc.code in (429,500,502,503,504) or (exc.code==403 and ("rate limit" in detail.lower() or exc.headers.get("X-RateLimit-Remaining")=="0"))
            if retryable and attempt<9:
                retry_after=exc.headers.get("Retry-After")
                try: delay=float(retry_after) if retry_after else min(2**attempt,120)
                except (TypeError,ValueError): delay=min(2**attempt,60)
                reset=exc.headers.get("X-RateLimit-Reset")
                if exc.code==403 and reset:
                    try: delay=max(delay,min(max(0,float(reset)-time.time()),120))
                    except (TypeError,ValueError): pass
                delay=max(1,min(delay,120))
                print("Q89_PERSIST_RETRY: HTTP "+str(exc.code)+" "+method+" "+path+" attempt "+str(attempt+1)+"/10 sleep="+str(delay)+"s")
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+method+" "+path+" "+detail) from exc
        except (http.client.IncompleteRead, http.client.RemoteDisconnected, ConnectionError, TimeoutError) as exc:
            if attempt<9:
                delay=min(2**attempt,60)
                print("Q89_PERSIST_RETRY: incomplete response "+method+" "+path+" attempt "+str(attempt+1)+"/10 sleep="+str(delay)+"s error="+repr(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: incomplete response after retries "+method+" "+path+" "+repr(exc)) from exc
        except urllib.error.URLError as exc:
            if attempt<9:
                delay=min(2**attempt,120)
                print("Q89_PERSIST_RETRY: network "+method+" "+path+" attempt "+str(attempt+1)+"/10 sleep="+str(delay)+"s error="+str(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q89_PERSIST_BLOCKED: network error "+method+" "+path+" "+str(exc)) from exc
    raise SystemExit("Q89_PERSIST_BLOCKED: API retry budget exhausted")
def sha256(data): return hashlib.sha256(data).hexdigest()
def git_blob_sha(data): return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()
def chunk_items(items,size):
    if size<1: raise ValueError("chunk size must be positive")
    return [items[i:i+size] for i in range(0,len(items),size)]

def is_mutable_output_path(path):
    return path in MUTABLE_OUTPUT_PATHS
def main():
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    report_path=OUT/"per_number_condition_9plus_grammar.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("task_id")!="Q89" or report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q89_PERSIST_BLOCKED: aggregate report not awaiting accepted validation")
    sys_path=str(ROOT/"scripts")
    import sys; sys.path.insert(0,sys_path)
    # Run the queue's fail-closed validator exactly once on the aggregate artifact.
    # Q89 is still AGGREGATED_PENDING_ACCEPTANCE_VALIDATION here; the validator accepts
    # that state and the queue marks it VALIDATED_PENDING_HUMAN_REVIEW only on success.
    subprocess.run(["python", str(ROOT/"scripts/sonar_research_queue.py")], cwd=ROOT, check=True)
    queue=json.loads((OUT/"research_queue_status.json").read_text(encoding="utf-8"))
    task=next((x for x in queue.get("tasks",[]) if x.get("id")=="Q89"),None)
    if queue.get("queue_status")!="QUEUE_VALID" or not task or task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"):
        raise SystemExit("Q89_PERSIST_BLOCKED: queue acceptance did not validate Q89")
    run_request=json.loads((OUT/"q89_run_request_2026-11-09.json").read_text(encoding="utf-8"))
    report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report["experiment_run_request_head_sha"]=run_request.get("run_request_commit_sha","be94053cd5c2a81bf2cca6ec8b74bee765a11d90")
    report["experiment_workflow_run_id"]=run_request.get("workflow_run_id",42668855015)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    run_id=os.environ.get("GITHUB_RUN_ID","unknown")
    archive_cutoff=report["last_date"]
    checkpoint={
      "schema_version":"1.0","project":"VinciCasa SONAR",
      "checkpoint_id":"SONAR-Q89-"+archive_cutoff+"-RUN-"+run_id,
      "status":"VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION","task_id":"Q89",
      "workflow_run_id":run_id,"created_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_checkout_head_sha":head,"experiment_run_request_head_sha":report.get("experiment_run_request_head_sha"),"experiment_workflow_run_id":report.get("experiment_workflow_run_id"),"source_archive_sha256":report["source_archive_sha256"],
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
    part_paths=[x["path"] for x in report.get("metrics_parts",[])]
    metadata_paths=[str(report_path.relative_to(ROOT)),
      "reports/sequence_agent/per_number_condition_9plus_formula_metrics_manifest.json",
      "reports/sequence_agent/per_number_condition_9plus_target_ledger.csv",
      "reports/sequence_agent/research_queue_status.json",
      str(checkpoint_path.relative_to(ROOT))]
    paths=part_paths+metadata_paths
    payloads={}
    for rel in paths:
        p=ROOT/rel
        if not p.is_file():
            raise SystemExit("Q89_PERSIST_BLOCKED: missing output "+rel)
        payloads[rel]=p.read_bytes()
    ref=api("GET","/git/ref/heads/"+BRANCH)
    if ref.get("object",{}).get("sha")!=head:
        raise SystemExit("Q89_PERSIST_BLOCKED: branch head differs from exact checkout; refusing stale write")
    current_tree=api("GET","/git/commits/"+head)["tree"]["sha"]
    current_doc=api("GET","/git/trees/"+current_tree+"?recursive=1")
    if current_doc.get("truncated"):
        raise SystemExit("Q89_PERSIST_BLOCKED: current tree truncated; cannot resume safely")
    current_map={x["path"]:x for x in current_doc.get("tree",[]) if x.get("type")=="blob"}
    expected={}; items=[]; already_verified=set()
    for rel,data in payloads.items():
        blob_sha=git_blob_sha(data)
        expected[rel]={"blob_sha":blob_sha,"bytes":len(data),"sha256":sha256(data)}
        existing=current_map.get(rel)
        if existing:
            if existing.get("sha")!=blob_sha or int(existing.get("size",-1))!=len(data):
                raise SystemExit("Q89_PERSIST_BLOCKED: existing immutable path conflicts with expected output: "+rel)
            blob=api("GET","/git/blobs/"+blob_sha); reread=base64.b64decode(blob["content"])
            if reread!=data or sha256(reread)!=sha256(data):
                raise SystemExit("Q89_PERSIST_BLOCKED: existing blob byte mismatch for "+rel)
            already_verified.add(rel)
            print("Q89_PERSIST_ALREADY_VERIFIED: "+rel+" bytes="+str(len(data)))
            continue
        blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
        if blob.get("sha")!=blob_sha:
            raise SystemExit("Q89_PERSIST_BLOCKED: Git blob SHA mismatch for "+rel)
        items.append({"path":rel,"data":data,"sha":blob_sha,"sha256":sha256(data)})
    def commit_chunk(parent_sha,base_tree,chunk,message):
        entries=[{"path":x["path"],"mode":"100644","type":"blob","sha":x["sha"]} for x in chunk]
        tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":entries}) if entries else {"sha":base_tree}
        commit=api("POST","/git/commits",{"message":message,"tree":tree["sha"],"parents":[parent_sha]})
        if api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]!=parent_sha:
            raise SystemExit("Q89_PERSIST_BLOCKED: branch advanced before chunk ref update")
        try:
            api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
        except SystemExit:
            current=api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]
            if current!=commit["sha"]:
                raise
            print("Q89_PERSIST_REF_UPDATE_VERIFIED_AFTER_TRANSIENT_RESPONSE")
        if api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]!=commit["sha"]:
            raise SystemExit("Q89_PERSIST_BLOCKED: chunk ref update did not persist")
        commit_doc=api("GET","/git/commits/"+commit["sha"])
        if commit_doc.get("tree",{}).get("sha")!=tree["sha"]:
            raise SystemExit("Q89_PERSIST_BLOCKED: chunk commit tree mismatch")
        for item in chunk:
            blob=api("GET","/git/blobs/"+item["sha"]); reread=base64.b64decode(blob["content"])
            if reread!=item["data"] or sha256(reread)!=item["sha256"]:
                raise SystemExit("Q89_PERSIST_BLOCKED: exact-byte reread mismatch for "+item["path"])
            print("Q89_PERSIST_VERIFIED: "+item["path"]+" bytes="+str(len(reread))+" commit="+commit["sha"])
        return commit["sha"],tree["sha"]
    metric_items=[x for x in items if "_formula_metrics_part_" in x["path"]]
    metadata_items=[x for x in items if x not in metric_items]
    chunks=chunk_items(metric_items,25)
    current_head=head
    for index,chunk in enumerate(chunks,1):
        current_head,current_tree=commit_chunk(current_head,current_tree,chunk,
            "Persist Q89 metric chunk "+str(index)+"/"+str(len(chunks))+" [q89-persist-chunk]")
        for item in chunk:
            current_map[item["path"]]={"path":item["path"],"type":"blob","sha":item["sha"],"size":len(item["data"])}
        print("Q89_PERSIST_CHUNK_COMPLETE: "+str(index)+"/"+str(len(chunks))+" head="+current_head)
    current_head,current_tree=commit_chunk(current_head,current_tree,metadata_items,
        "Persist validated Q89 nine-feature outputs [q89-persisted]")
    final_tree=api("GET","/git/trees/"+current_tree+"?recursive=1")
    if final_tree.get("truncated"):
        raise SystemExit("Q89_PERSIST_BLOCKED: final persisted tree truncated")
    final_map={x["path"]:x for x in final_tree.get("tree",[]) if x.get("type")=="blob"}
    for rel,data in payloads.items():
        entry=final_map.get(rel)
        if not entry or entry.get("sha")!=expected[rel]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q89_PERSIST_BLOCKED: final commit tree mismatch for "+rel)
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as h:
            h.write("commit_created=true\ncommit_sha="+current_head+"\n")
    print(json.dumps({"task_id":"Q89","persisted_head_sha":current_head,"parent_sha":head,
      "verified_file_count":len(payloads),"already_present_count":len(already_verified),
      "verified_bytes":sum(map(len,payloads.values())),"all_exact_commit_bytes_verified":True,
      "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
if __name__=="__main__": main()
