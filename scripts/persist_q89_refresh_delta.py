#!/usr/bin/env python3
"""Append-only Git Data API persistence and exact-byte readback for Q89 refresh outputs."""
from __future__ import annotations
import base64,hashlib,http.client,json,os,time,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
BRANCH=os.environ.get("SONAR_BRANCH","research/sonar-q92-ten-feature-implementation-20261109")
API="https://api.github.com"
DELTA_DIR=OUT/"q89_refresh_20261108_delta_shards"

def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN")
    repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token: raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    for attempt in range(7):
        request=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
            "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
            "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q89-refresh-persistence"})
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
                delay=max(1,min(delay,60))
                print("Q89_REFRESH_PERSIST_RETRY: HTTP "+str(exc.code)+" attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s")
                time.sleep(delay);continue
            raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+detail) from exc
        except (http.client.IncompleteRead,http.client.RemoteDisconnected,ConnectionError,TimeoutError,urllib.error.URLError) as exc:
            if attempt<6:
                delay=min(2**attempt,60)
                print("Q89_REFRESH_PERSIST_RETRY: transport attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s error="+repr(exc))
                time.sleep(delay);continue
            raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: transport retry budget exhausted "+repr(exc)) from exc
    raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: API retry budget exhausted")

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def blob_bytes(sha):
    blob=api("GET","/git/blobs/"+sha)
    if blob.get("encoding")!="base64": raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: Git blob encoding mismatch")
    return base64.b64decode(blob["content"])

def current_tree_map(commit_sha):
    commit=api("GET","/git/commits/"+commit_sha)
    tree=api("GET","/git/trees/"+commit["tree"]["sha"]+"?recursive=1")
    if tree.get("truncated"): raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: Git tree truncated")
    return commit["tree"]["sha"],{item["path"]:item for item in tree.get("tree",[]) if item.get("type")=="blob"}

def commit_payloads(head,payloads,message):
    branch_ref=api("GET","/git/ref/heads/"+BRANCH)
    if branch_ref.get("object",{}).get("sha")!=head:
        raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: branch head differs from expected checkout; refusing stale write")
    base_tree,current_map=current_tree_map(head)
    elements=[]
    expected={}
    for relative,data in payloads.items():
        existing=current_map.get(relative)
        if existing:
            old=blob_bytes(existing["sha"])
            if old!=data:
                raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: append-only path exists with different bytes: "+relative)
            blob_sha=existing["sha"]
        else:
            blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
            blob_sha=blob["sha"]
        elements.append({"path":relative,"mode":"100644","type":"blob","sha":blob_sha})
        expected[relative]={"blob_sha":blob_sha,"bytes":len(data),"sha256":sha256(data)}
    tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":elements})
    commit=api("POST","/git/commits",{"message":message,"tree":tree["sha"],"parents":[head]})
    if api("GET","/git/ref/heads/"+BRANCH).get("object",{}).get("sha")!=head:
        raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: branch advanced during Git Data API commit; refusing ref update")
    try:
        api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
    except SystemExit:
        current=api("GET","/git/ref/heads/"+BRANCH)
        if current.get("object",{}).get("sha")!=commit["sha"]: raise
        print("Q89_REFRESH_PERSIST_REF_UPDATE_VERIFIED_AFTER_TRANSIENT_RESPONSE")
    _,persisted_map=current_tree_map(commit["sha"])
    verified_bytes=0
    for relative,data in payloads.items():
        entry=persisted_map.get(relative)
        if not entry or entry.get("sha")!=expected[relative]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: persisted tree entry mismatch "+relative)
        reread=blob_bytes(entry["sha"])
        if reread!=data or sha256(reread)!=expected[relative]["sha256"]:
            raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: exact-byte reread mismatch "+relative)
        verified_bytes+=len(data)
        print("Q89_REFRESH_PERSIST_VERIFIED: "+relative+" bytes="+str(len(data)))
    return commit["sha"],len(payloads),verified_bytes

def main():
    head=os.environ.get("GITHUB_SHA")
    if not head:
        import subprocess
        head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    report_path=OUT/"q89_refresh_20261108_report.json"
    manifest_path=OUT/"q89_refresh_20261108_manifest.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION" or manifest.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: aggregate report/manifest not pending acceptance")
    # Acceptance was run immediately before persistence on this exact checkout.
    report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report["review_status"]="PENDING_HUMAN_REVIEW_INTEGRATION"
    manifest["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    run_id=os.environ.get("GITHUB_RUN_ID","unknown")
    paths=[
      str(report_path.relative_to(ROOT)),str(manifest_path.relative_to(ROOT)),
      "reports/sequence_agent/q89_refresh_20261108_target_delta_ledger.csv",
      "reports/sequence_agent/q89_refresh_20261108_candidate_shortlist.csv",
      "reports/sequence_agent/q89_refresh_20261108_candidate_selection.json"]
    paths.extend(item["path"] for item in manifest.get("parts",[]))
    payloads={}
    for relative in paths:
        path=ROOT/relative
        if not path.is_file(): raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: missing output "+relative)
        payloads[relative]=path.read_bytes()
    run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT","1")\n    checkpoint_relative="reports/sequence_agent/q89_refresh_20261108_checkpoint_run_"+run_id+"_attempt_"+run_attempt+"_pre_readback.json"
    checkpoint={
      "schema_version":"1.0","project":"VinciCasa SONAR","task_id":"Q89_REFRESH_2026_11_08",
      "checkpoint_id":"SONAR-Q89-REFRESH-2026-11-08-RUN-"+run_id+"-ATTEMPT-"+run_attempt,
      "status":"PERSISTED_READBACK_PENDING","workflow_run_id":run_id,"created_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_checkout_head_sha":head,"canonical_archive_main_commit":report["source_archive_main_commit"],
      "source_archive_sha256":report["source_archive_sha256"],"source_archive_git_blob_sha1":report["source_archive_git_blob_sha1"],
      "target_count":report["target_count"],"scored_targets":report["scored_targets"],"split_counts":report["split_counts"],
      "formula_count":report["formula_count"],"delta_shard_count":report["shard_count"],"holm_family_size":report["multiple_testing"]["test_count"],
      "holm_adjusted_rows_below_0_05":report["multiple_testing"]["holm_adjusted_formula_split_rows_below_0_05"],
      "minimum_holm_p_max_endpoint_family":report["multiple_testing"]["minimum_holm_p_max_endpoint_family"],
      "selected_q89_candidate_id":report["candidate_selection"]["selected_candidate_id"],
      "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
      "guardrails":["Q89 base metrics and 2026-11-07 freeze preserved","delta targets scored strictly prior-only","Discovery/Validation selection frozen before Blind OOS",
        "no automatic merge, engine promotion or shadow insertion","PRs #6/#7/#8 untouched"]}
    payloads[checkpoint_relative]=json.dumps(checkpoint,ensure_ascii=False,indent=2).encode("utf-8")+b"\n"
    first_commit,file_count,verified_bytes=commit_payloads(head,payloads,"Persist accepted Q89 2026-11-08 incremental refresh outputs and delta ledger [q89-refresh-delta-persisted]")
    checkpoint["status"]="VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION"
    checkpoint["persisted_commit_sha"]=first_commit
    checkpoint["persisted_parent_sha"]=head
    checkpoint["verified_file_count"]=file_count
    checkpoint["verified_bytes"]=verified_bytes
    checkpoint["all_exact_commit_bytes_verified"]=True
    checkpoint["readback_verified_at_utc"]=datetime.now(timezone.utc).isoformat()
    final_checkpoint=json.dumps(checkpoint,ensure_ascii=False,indent=2).encode("utf-8")+b"\n"
    final_checkpoint_relative=checkpoint_relative.replace("_pre_readback.json","_verified.json")\n    final_payload={final_checkpoint_relative:final_checkpoint}
    final_commit,final_count,final_bytes=commit_payloads(first_commit,final_payload,"Finalize Q89 refresh exact-byte readback checkpoint [q89-refresh-delta-checkpoint]")
    if final_count!=1 or final_bytes!=len(final_checkpoint):
        raise SystemExit("Q89_REFRESH_PERSIST_BLOCKED: final checkpoint readback dimensions mismatch")
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as handle:
            handle.write("commit_created=true\ncommit_sha="+final_commit+"\n")
    print(json.dumps({"task_id":"Q89_REFRESH_2026_11_08","persisted_head_sha":final_commit,"parent_sha":first_commit,
      "verified_file_count":file_count+final_count,"verified_bytes":verified_bytes+final_bytes,
      "all_exact_commit_bytes_verified":True,"review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))

if __name__=="__main__":
    main()
