#!/usr/bin/env python3
"""Append-only Git Data API persistence for fully validated Q89 outputs with exact-byte reread."""
from __future__ import annotations
import base64, hashlib, http.client, json, os, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRANCH="research/sonar-q89-nine-feature-20261108"
OUT=ROOT/"reports/sequence_agent"
API="https://api.github.com"
QUEUE_STATUS_RELATIVE="reports/sequence_agent/research_queue_status.json"
QUEUE_STATUS_EXPECTED_BLOB_SHA="9944646da4c14b3f4958bdfe9108f318177837b5"

def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN")
    repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token:
        raise SystemExit("Q89_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    for attempt in range(7):
        request=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
            "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
            "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q89-persistence"})
        try:
            with urllib.request.urlopen(request,timeout=300) as response:
                raw=response.read()
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
        except (http.client.IncompleteRead,http.client.RemoteDisconnected,ConnectionError,TimeoutError) as exc:
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

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def inspect_existing_payloads(payloads,current_map,read_blob,preloaded=None):
    """Read current Git blobs once; return whether every append-only payload is already exact."""
    cached=dict(preloaded or {})
    all_exact=True
    for relative,data in payloads.items():
        entry=current_map.get(relative)
        if not entry:
            all_exact=False
            continue
        remote_bytes=cached.get(relative)
        if remote_bytes is None:
            remote_bytes=read_blob(entry["sha"])
            cached[relative]=remote_bytes
        if remote_bytes!=data or int(entry.get("size",-1))!=len(data) or sha256(remote_bytes)!=sha256(data):
            all_exact=False
    return all_exact,cached

def blob_bytes(sha):
    blob=api("GET","/git/blobs/"+sha)
    if blob.get("encoding")!="base64":
        raise SystemExit("Q89_PERSIST_BLOCKED: Git blob encoding mismatch")
    return base64.b64decode(blob["content"])

def validate_queue_status_append(existing_bytes,new_bytes,existing_blob_sha):
    if existing_blob_sha!=QUEUE_STATUS_EXPECTED_BLOB_SHA:
        return False,"unexpected existing queue blob SHA"
    try:
        old=json.loads(existing_bytes.decode("utf-8"))
        new=json.loads(new_bytes.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        return False,"queue JSON decode failure: "+str(exc)
    old_tasks=old.get("tasks")
    new_tasks=new.get("tasks")
    if not isinstance(old_tasks,list) or not isinstance(new_tasks,list):
        return False,"queue task arrays are missing"
    if new_tasks[:-1]!=old_tasks or len(new_tasks)!=len(old_tasks)+1:
        return False,"existing task records are not preserved exactly with one appended task"
    q89_task=new_tasks[-1]
    if q89_task.get("id")!="Q89":
        return False,"the only appended task is not Q89"
    if q89_task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW":
        return False,"Q89 is not pending human review"
    if q89_task.get("missing_evidence") or q89_task.get("validation_errors"):
        return False,"Q89 queue acceptance has missing evidence or validation errors"
    if q89_task.get("depends_on")!=["Q00","Q88"]:
        return False,"Q89 dependency contract changed"
    if old.get("queue_status")!="QUEUE_VALID" or new.get("queue_status")!="QUEUE_VALID":
        return False,"queue status is not valid"
    if new.get("task_count")!=old.get("task_count",0)+1:
        return False,"queue task count did not increase by exactly one"
    for key,value in old.items():
        if key in ("generated_at_utc","task_count","tasks"):
            continue
        if new.get(key)!=value:
            return False,"top-level queue field changed unexpectedly: "+key
    return True,""

def main():
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    report_path=OUT/"per_number_condition_9plus_grammar.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("task_id")!="Q89" or report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q89_PERSIST_BLOCKED: aggregate report is not awaiting acceptance validation")
    # The aggregate workflow already passed Q89 acceptance while status was AGGREGATED_PENDING_ACCEPTANCE_VALIDATION.
    # Set the technical review status, then let the fail-closed queue validator re-run acceptance on this exact output.
    report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report["review_status"]="PENDING_HUMAN_REVIEW_INTEGRATION"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    subprocess.run([sys.executable,str(ROOT/"scripts/sonar_research_queue.py")],cwd=ROOT,check=True)
    queue_path=OUT/"research_queue_status.json"
    local_queue=json.loads(queue_path.read_text(encoding="utf-8"))
    q89_task=next((task for task in local_queue.get("tasks",[]) if task.get("id")=="Q89"),None)
    if local_queue.get("queue_status")!="QUEUE_VALID" or not q89_task or q89_task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or q89_task.get("validation_errors"):
        raise SystemExit("Q89_PERSIST_BLOCKED: research queue is not validated/pending human review")
    run_id=os.environ.get("GITHUB_RUN_ID","unknown")
    checkpoint={
      "schema_version":"1.0","project":"VinciCasa SONAR",
      "checkpoint_id":"SONAR-Q89-2026-11-07-RUN-"+run_id,
      "status":"VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION","task_id":"Q89",
      "workflow_run_id":run_id,"created_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_checkout_head_sha":head,"source_archive_sha256":report["source_archive_sha256"],
      "target_count":report["target_count"],"scored_targets":report["scored_targets"],
      "first_date":report["first_date"],"last_date":report["last_date"],
      "formula_count":report["formula_count"],"metrics_rows":report["metrics_rows"],
      "target_ledger_rows":report["target_ledger_rows"],"shard_count":report["shard_count"],
      "global_holm_test_count":report["multiple_testing"]["test_count"],
      "metrics_manifest_sha256":json.loads((OUT/"per_number_condition_9plus_formula_metrics_manifest.json").read_text(encoding="utf-8"))["parts_manifest_sha256"],
      "selected_candidate_ids":{"Q89":report["candidate_selection"]["Q89_formula_id"],"Q88":report["candidate_selection"]["Q88_control_formula_id"]},
      "paired_blind_inference_status":json.loads((OUT/"per_number_condition_9plus_paired_inference.json").read_text(encoding="utf-8"))["decision"],
      "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
      "guardrails":["no automatic merge","no engine promotion","no shadow-stream insertion","no immutable freeze overwritten","human review/integration required"]}
    checkpoint_path=OUT/"q89_checkpoint_2026-11-08.json"
    checkpoint_path.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    paths=[str(report_path.relative_to(ROOT)),
      "reports/sequence_agent/per_number_condition_9plus_formula_metrics_manifest.json",
      "reports/sequence_agent/per_number_condition_9plus_target_ledger.csv",
      "reports/sequence_agent/per_number_condition_9plus_candidate_shortlist.csv",
      "reports/sequence_agent/per_number_condition_9plus_candidate_selection.json",
      "reports/sequence_agent/q89_selected_candidate_blind_ledger.csv",
      "reports/sequence_agent/per_number_condition_9plus_paired_inference.json",
      "reports/sequence_agent/research_queue_status.json",
      str(checkpoint_path.relative_to(ROOT))]
    paths.extend(item["path"] for item in report.get("metrics_parts",[]))
    payloads={}
    for relative in paths:
        path=ROOT/relative
        if not path.is_file():
            raise SystemExit("Q89_PERSIST_BLOCKED: missing output "+relative)
        payloads[relative]=path.read_bytes()
    branch_ref=api("GET","/git/ref/heads/"+BRANCH)
    if branch_ref.get("object",{}).get("sha")!=head:
        raise SystemExit("Q89_PERSIST_BLOCKED: branch head differs from exact checkout; refusing stale write")
    base_commit=api("GET","/git/commits/"+head)
    base_tree=base_commit["tree"]["sha"]
    current_tree=api("GET","/git/trees/"+base_tree+"?recursive=1")
    if current_tree.get("truncated"):
        raise SystemExit("Q89_PERSIST_BLOCKED: base tree is truncated")
    current_map={item["path"]:item for item in current_tree.get("tree",[]) if item.get("type")=="blob"}
    existing_bytes_cache={}
    # Q89 queue status is mutable, unlike immutable target freezes. Allow only a guarded one-task append
    # against the exact preregistered queue blob; an idempotent retry retains the first accepted snapshot.
    queue_relative=QUEUE_STATUS_RELATIVE
    queue_update_allowed=False
    if queue_relative in current_map:
        existing_queue_sha=current_map[queue_relative]["sha"]
        remote_queue_bytes=blob_bytes(existing_queue_sha)
        existing_bytes_cache[queue_relative]=remote_queue_bytes
        remote_queue=json.loads(remote_queue_bytes.decode("utf-8"))
        remote_q89=next((task for task in remote_queue.get("tasks",[]) if task.get("id")=="Q89"),None)
        if remote_q89:
            if remote_q89!=q89_task or remote_q89.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or remote_q89.get("missing_evidence") or remote_q89.get("validation_errors"):
                raise SystemExit("Q89_PERSIST_BLOCKED: existing queue Q89 status conflicts with local validated evidence")
            if remote_queue.get("tasks")!=local_queue.get("tasks"):
                raise SystemExit("Q89_PERSIST_BLOCKED: existing queue task catalog differs from local validated catalog")
            payloads[queue_relative]=remote_queue_bytes
        else:
            allowed,reason=validate_queue_status_append(remote_queue_bytes,payloads[queue_relative],existing_queue_sha)
            if not allowed:
                raise SystemExit("Q89_PERSIST_BLOCKED: queue status append guard: "+reason)
            queue_update_allowed=True
    # Idempotent append-only retry: retain the first accepted checkpoint at its preregistered path.
    checkpoint_relative="reports/sequence_agent/q89_checkpoint_2026-11-08.json"
    if checkpoint_relative in current_map:
        remote_checkpoint_bytes=blob_bytes(current_map[checkpoint_relative]["sha"])
        existing_bytes_cache[checkpoint_relative]=remote_checkpoint_bytes
        remote_checkpoint=json.loads(remote_checkpoint_bytes.decode("utf-8"))
        if remote_checkpoint.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION" or remote_checkpoint.get("source_archive_sha256")!=report.get("source_archive_sha256") or remote_checkpoint.get("formula_count")!=report.get("formula_count"):
            raise SystemExit("Q89_PERSIST_BLOCKED: existing checkpoint conflicts with accepted Q89 evidence")
        payloads[checkpoint_relative]=remote_checkpoint_bytes
    all_payloads_exact,existing_bytes_cache=inspect_existing_payloads(payloads,current_map,blob_bytes,existing_bytes_cache)
    if all_payloads_exact:
        verified_bytes=0
        for relative,data in payloads.items():
            entry=current_map[relative]
            reread=existing_bytes_cache[relative]
            if reread!=data or int(entry.get("size",-1))!=len(data) or sha256(reread)!=sha256(data):
                raise SystemExit("Q89_PERSIST_BLOCKED: idempotent exact-byte readback mismatch for "+relative)
            verified_bytes+=len(reread)
            print("Q89_PERSIST_VERIFIED: "+relative+" bytes="+str(len(data)))
        output=os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output,"a",encoding="utf-8") as handle:
                handle.write("commit_created=false\\ncommit_sha="+head+"\\n")
        print(json.dumps({"task_id":"Q89","persisted_head_sha":head,"parent_sha":head,
          "verified_file_count":len(payloads),"verified_bytes":verified_bytes,
          "all_exact_commit_bytes_verified":True,"idempotent_retry":True,
          "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
        return

    elements=[]
    expected={}
    for relative,data in payloads.items():
        existing=current_map.get(relative)
        changed=False
        if existing:
            existing_bytes=existing_bytes_cache.get(relative)
            if existing_bytes is None:
                existing_bytes=blob_bytes(existing["sha"])
                existing_bytes_cache[relative]=existing_bytes
            if existing_bytes==data:
                blob_sha=existing["sha"]
            elif relative==queue_relative and queue_update_allowed:
                blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
                blob_sha=blob["sha"]
                changed=True
            else:
                raise SystemExit("Q89_PERSIST_BLOCKED: append-only path already exists with different bytes: "+relative)
        else:
            blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
            blob_sha=blob["sha"]
            changed=True
        if changed:
            elements.append({"path":relative,"mode":"100644","type":"blob","sha":blob_sha})
        expected[relative]={"blob_sha":blob_sha,"bytes":len(data),"sha256":sha256(data)}
    if not elements:
        raise SystemExit("Q89_PERSIST_BLOCKED: no tree changes planned but payload readback was not exact")
    tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":elements})
    commit=api("POST","/git/commits",{"message":"Persist validated Q89 nine-feature formula catalog, global Holm family and paired blind OOS checkpoint [q89-persisted]","tree":tree["sha"],"parents":[head]})
    if api("GET","/git/ref/heads/"+BRANCH).get("object",{}).get("sha")!=head:
        raise SystemExit("Q89_PERSIST_BLOCKED: branch advanced during persistence; refusing ref update")
    try:
        api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
    except SystemExit:
        current=api("GET","/git/ref/heads/"+BRANCH)
        if current.get("object",{}).get("sha")!=commit["sha"]:
            raise
        print("Q89_PERSIST_REF_UPDATE_VERIFIED_AFTER_TRANSIENT_RESPONSE")
    committed=api("GET","/git/commits/"+commit["sha"])
    persisted_tree=api("GET","/git/trees/"+committed["tree"]["sha"]+"?recursive=1")
    if persisted_tree.get("truncated"):
        raise SystemExit("Q89_PERSIST_BLOCKED: persisted tree truncated")
    persisted_map={item["path"]:item for item in persisted_tree.get("tree",[]) if item.get("type")=="blob"}
    verified_bytes=0
    for relative,data in payloads.items():
        entry=persisted_map.get(relative)
        if not entry or entry.get("sha")!=expected[relative]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q89_PERSIST_BLOCKED: exact commit tree mismatch for "+relative)
        reread=blob_bytes(entry["sha"])
        if reread!=data or sha256(reread)!=expected[relative]["sha256"]:
            raise SystemExit("Q89_PERSIST_BLOCKED: exact-byte reread mismatch for "+relative)
        verified_bytes+=len(data)
        print("Q89_PERSIST_VERIFIED: "+relative+" bytes="+str(len(data)))
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as handle:
            handle.write("commit_created=true\ncommit_sha="+commit["sha"]+"\n")
    print(json.dumps({"task_id":"Q89","persisted_head_sha":commit["sha"],"parent_sha":head,
      "verified_file_count":len(payloads),"verified_bytes":verified_bytes,
      "all_exact_commit_bytes_verified":True,"review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
if __name__=="__main__":
    main()
