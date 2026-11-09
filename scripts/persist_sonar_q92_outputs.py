#!/usr/bin/env python3
"""Append-only chunked Git Data API persistence for acceptance-validated Q92 outputs."""
from __future__ import annotations
import base64,concurrent.futures,hashlib,http.client,json,os,subprocess,sys,time,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRANCH="research/sonar-q92-ten-feature-prereg-20261109"
OUT=ROOT/"reports/sequence_agent"
API="https://api.github.com"
TREE_CHUNK_SIZE=50
READBACK_WORKERS=12

REPORT_PATH=OUT/"per_number_condition_10plus_grammar.json"
MANIFEST_PATH=OUT/"per_number_condition_10plus_formula_metrics_manifest.json"
LEDGER_PATH=OUT/"per_number_condition_10plus_target_ledger.csv"
SHORTLIST_PATH=OUT/"per_number_condition_10plus_candidate_shortlist.csv"
SELECTION_PATH=OUT/"per_number_condition_10plus_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q92_selected_candidate_blind_ledger.csv"
PAIRED_INFERENCE_PATH=OUT/"per_number_condition_10plus_paired_inference.json"
Q89_REFRESH_CONTROL_PATHS=[
    "reports/sequence_agent/q89_refresh_20261108_report.json",
    "reports/sequence_agent/q89_refresh_20261108_manifest.json",
    "reports/sequence_agent/q89_refresh_20261108_candidate_selection.json",
    "reports/sequence_agent/q89_refresh_20261108_selected_candidate_blind_ledger.csv"
]

def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN")
    repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token:
        raise SystemExit("Q92_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    for attempt in range(7):
        request=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
            "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
            "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q92-persistence"})
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
                print("Q92_PERSIST_RETRY: HTTP "+str(exc.code)+" attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s")
                time.sleep(delay)
                continue
            raise SystemExit("Q92_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+detail) from exc
        except (http.client.IncompleteRead,http.client.RemoteDisconnected,ConnectionError,TimeoutError) as exc:
            if attempt<6:
                delay=min(2**attempt,60)
                print("Q92_PERSIST_RETRY: incomplete response attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s error="+repr(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q92_PERSIST_BLOCKED: incomplete response after retries "+repr(exc)) from exc
        except urllib.error.URLError as exc:
            if attempt<6:
                delay=min(2**attempt,60)
                print("Q92_PERSIST_RETRY: network attempt "+str(attempt+1)+"/7 sleep="+str(delay)+"s error="+str(exc))
                time.sleep(delay)
                continue
            raise SystemExit("Q92_PERSIST_BLOCKED: network error "+str(exc)) from exc
    raise SystemExit("Q92_PERSIST_BLOCKED: API retry budget exhausted")

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def tree_batches(elements,limit=TREE_CHUNK_SIZE):
    if limit<1:
        raise ValueError("tree batch limit must be positive")
    return [elements[index:index+limit] for index in range(0,len(elements),limit)]

def blob_bytes(sha):
    blob=api("GET","/git/blobs/"+sha)
    if blob.get("encoding")!="base64":
        raise SystemExit("Q92_PERSIST_BLOCKED: Git blob encoding mismatch")
    return base64.b64decode(blob["content"])

def plan_payloads(payloads,current_map,read_blob,create_blob):
    """Fail closed on changed append-only paths; create blobs only for missing paths."""
    expected={}
    elements=[]
    all_exact=True
    for relative,data in payloads.items():
        existing=current_map.get(relative)
        if existing:
            remote_bytes=read_blob(existing["sha"])
            if remote_bytes!=data or int(existing.get("size",-1))!=len(data) or sha256(remote_bytes)!=sha256(data) or git_blob_sha1(remote_bytes)!=existing["sha"]:
                raise SystemExit("Q92_PERSIST_BLOCKED: append-only path exists with different bytes: "+relative)
            blob_sha=existing["sha"]
        else:
            all_exact=False
            blob_sha=create_blob(data)
            elements.append({"path":relative,"mode":"100644","type":"blob","sha":blob_sha})
        expected[relative]={"blob_sha":blob_sha,"bytes":len(data),"sha256":sha256(data),"git_blob_sha1":git_blob_sha1(data)}
    return expected,elements,all_exact

def create_blob(data):
    blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
    if blob.get("sha")!=git_blob_sha1(data):
        raise SystemExit("Q92_PERSIST_BLOCKED: created Git blob SHA1 mismatch")
    return blob["sha"]

def create_tree_chunked(base_tree,elements,limit=TREE_CHUNK_SIZE):
    tree_sha=base_tree
    batches=tree_batches(elements,limit)
    for index,batch in enumerate(batches):
        tree=api("POST","/git/trees",{"base_tree":tree_sha,"tree":batch})
        tree_sha=tree["sha"]
        print("Q92_PERSIST_TREE_BATCH: "+str(index+1)+"/"+str(len(batches))+" entries="+str(len(batch))+" tree="+tree_sha)
    return tree_sha,len(batches)

def readback_payloads(commit_sha,expected,payloads):
    commit=api("GET","/git/commits/"+commit_sha)
    tree=api("GET","/git/trees/"+commit["tree"]["sha"]+"?recursive=1")
    if tree.get("truncated"):
        raise SystemExit("Q92_PERSIST_BLOCKED: persisted tree is truncated")
    current={item["path"]:item for item in tree.get("tree",[]) if item.get("type")=="blob"}
    def verify_one(relative):
        want=expected[relative]
        entry=current.get(relative)
        if not entry or entry.get("sha")!=want["blob_sha"] or int(entry.get("size",-1))!=want["bytes"]:
            raise SystemExit("Q92_PERSIST_BLOCKED: persisted tree entry mismatch for "+relative)
        remote=blob_bytes(entry["sha"])
        local=payloads[relative]
        if remote!=local or sha256(remote)!=want["sha256"] or git_blob_sha1(remote)!=want["git_blob_sha1"] or len(remote)!=want["bytes"]:
            raise SystemExit("Q92_PERSIST_BLOCKED: exact-byte readback mismatch for "+relative)
        return len(remote)
    total=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=READBACK_WORKERS) as pool:
        for size in pool.map(verify_one,list(expected.keys())):
            total+=size
    return len(expected),total,tree["sha"]

def make_checkpoint(report,run_id,attempt,head,status,extra=None):
    checkpoint={
        "schema_version":"1.0","project":"VinciCasa SONAR",
        "checkpoint_id":"SONAR-Q92-2026-11-08-RUN-"+run_id+"-ATTEMPT-"+attempt+"-"+status,
        "status":status,"task_id":"Q92","workflow_run_id":run_id,"workflow_run_attempt":attempt,
        "created_at_utc":datetime.now(timezone.utc).isoformat(),"source_checkout_head_sha":head,
        "source_archive_sha256":report["source_archive_sha256"],"source_archive_git_blob_sha1":report["source_archive_git_blob_sha1"],
        "source_archive_main_commit":report["source_archive_main_commit"],"target_count":report["target_count"],
        "scored_targets":report["scored_targets"],"first_date":report["first_date"],"last_date":report["last_date"],
        "formula_count":report["formula_count"],"metrics_rows":report["metrics_rows"],"target_ledger_rows":report["target_ledger_rows"],
        "shard_count":report["shard_count"],"global_holm_test_count":report["multiple_testing"]["test_count"],
        "metrics_manifest_sha256":json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["parts_manifest_sha256"],
        "selected_candidate_ids":{"Q92":report["candidate_selection"]["Q92_formula_id"],"Q89_control":report["candidate_selection"]["Q89_control_formula_id"]},
        "paired_blind_inference_decision":json.loads(PAIRED_INFERENCE_PATH.read_text(encoding="utf-8"))["decision"],
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
        "guardrails":["no automatic merge","no engine promotion","no shadow-stream insertion","no immutable freeze overwritten","human review/integration required"]}
    if extra:
        checkpoint.update(extra)
    return checkpoint

def main():
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"]!=head:
        raise SystemExit("Q92_PERSIST_BLOCKED: GITHUB_SHA differs from exact checkout HEAD")
    if os.environ.get("Q92_ACCEPTANCE_VALIDATED")!="true":
        raise SystemExit("Q92_PERSIST_BLOCKED: acceptance validator success marker missing")
    report=json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    manifest=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if report.get("task_id")!="Q92" or report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        raise SystemExit("Q92_PERSIST_BLOCKED: aggregate report is not awaiting acceptance validation")
    if manifest.get("task_id")!="Q92" or manifest.get("formula_count")!=report.get("formula_count") or manifest.get("metrics_rows")!=report.get("metrics_rows"):
        raise SystemExit("Q92_PERSIST_BLOCKED: metrics manifest identity/dimensions mismatch")
    report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    report["review_status"]="PENDING_HUMAN_REVIEW_INTEGRATION"
    manifest["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    run_id=os.environ.get("GITHUB_RUN_ID","unknown")
    attempt=os.environ.get("GITHUB_RUN_ATTEMPT","1")
    pre_relative="reports/sequence_agent/q92_checkpoint_run_"+run_id+"_attempt_"+attempt+"_pre_readback.json"
    verified_relative="reports/sequence_agent/q92_checkpoint_run_"+run_id+"_attempt_"+attempt+"_verified.json"
    pre_path=ROOT/pre_relative
    verified_path=ROOT/verified_relative
    # Reuse an immutable pre-readback checkpoint on an idempotent retry.
    branch_ref=api("GET","/git/ref/heads/"+BRANCH)
    if branch_ref.get("object",{}).get("sha")!=head:
        raise SystemExit("Q92_PERSIST_BLOCKED: branch head differs from exact checkout; refusing stale write")
    base_commit=api("GET","/git/commits/"+head)
    base_tree=base_commit["tree"]["sha"]
    current_tree=api("GET","/git/trees/"+base_tree+"?recursive=1")
    if current_tree.get("truncated"):
        raise SystemExit("Q92_PERSIST_BLOCKED: base tree is truncated")
    current_map={item["path"]:item for item in current_tree.get("tree",[]) if item.get("type")=="blob"}
    if pre_relative in current_map:
        pre_bytes=blob_bytes(current_map[pre_relative]["sha"])
        pre_checkpoint=json.loads(pre_bytes.decode("utf-8"))
        if pre_checkpoint.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION" or pre_checkpoint.get("source_archive_sha256")!=report.get("source_archive_sha256"):
            raise SystemExit("Q92_PERSIST_BLOCKED: existing pre-readback checkpoint conflicts")
        pre_path.write_bytes(pre_bytes)
    else:
        pre_checkpoint=make_checkpoint(report,run_id,attempt,head,"VALIDATED_PENDING_HUMAN_REVIEW_INTEGRATION",
            {"readback_status":"PENDING","acceptance_validator":"scripts/sonar_q92_acceptance.py"})
        pre_path.write_text(json.dumps(pre_checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    paths=[
        str(REPORT_PATH.relative_to(ROOT)),str(MANIFEST_PATH.relative_to(ROOT)),str(LEDGER_PATH.relative_to(ROOT)),
        str(SHORTLIST_PATH.relative_to(ROOT)),str(SELECTION_PATH.relative_to(ROOT)),str(PAIRED_LEDGER_PATH.relative_to(ROOT)),
        str(PAIRED_INFERENCE_PATH.relative_to(ROOT)),pre_relative]
    paths.extend(Q89_REFRESH_CONTROL_PATHS)
    paths.extend(item["path"] for item in report.get("metrics_parts",[]))
    if len(paths)!=len(set(paths)):
        raise SystemExit("Q92_PERSIST_BLOCKED: duplicate output paths")
    payloads={}
    for relative in paths:
        path=ROOT/relative
        if not path.is_file():
            raise SystemExit("Q92_PERSIST_BLOCKED: missing output "+relative)
        payloads[relative]=path.read_bytes()
    expected,elements,all_exact=plan_payloads(payloads,current_map,blob_bytes,create_blob)
    created_commit=False
    first_commit=head
    if elements:
        final_tree,tree_batches_count=create_tree_chunked(base_tree,elements,TREE_CHUNK_SIZE)
        commit=api("POST","/git/commits",{"message":"Persist acceptance-validated Q92 ten-feature outputs append-only [q92-persist]","tree":final_tree,"parents":[head]})
        new_sha=commit["sha"]
        branch_ref=api("GET","/git/ref/heads/"+BRANCH)
        if branch_ref.get("object",{}).get("sha")!=head:
            raise SystemExit("Q92_PERSIST_BLOCKED: branch head advanced before ref update")
        api("PATCH","/git/refs/heads/"+BRANCH,{"sha":new_sha,"force":False})
        check_ref=api("GET","/git/ref/heads/"+BRANCH)
        if check_ref.get("object",{}).get("sha")!=new_sha:
            raise SystemExit("Q92_PERSIST_BLOCKED: output commit ref readback mismatch")
        first_commit=new_sha
        created_commit=True
        print("Q92_PERSIST_COMMIT: "+new_sha+" tree_batches="+str(tree_batches_count)+" new_paths="+str(len(elements)))
    file_count,total_bytes,readback_tree_sha=readback_payloads(first_commit,expected,payloads)
    print("Q92_PERSIST_READBACK_VERIFIED: commit="+first_commit+" files="+str(file_count)+" bytes="+str(total_bytes)+" tree="+readback_tree_sha)
    # The post-readback checkpoint is a new append-only path, never an overwrite.
    if verified_relative in current_map:
        remote_verified=blob_bytes(current_map[verified_relative]["sha"])
        remote_checkpoint=json.loads(remote_verified.decode("utf-8"))
        if remote_checkpoint.get("status")!="PERSISTED_READBACK_VERIFIED_PENDING_HUMAN_REVIEW" or remote_checkpoint.get("source_archive_sha256")!=report.get("source_archive_sha256") or remote_checkpoint.get("all_output_bytes_exact") is not True or int(remote_checkpoint.get("verified_file_count",-1))!=file_count or int(remote_checkpoint.get("verified_bytes",-1))!=total_bytes:
            raise SystemExit("Q92_PERSIST_BLOCKED: existing verified checkpoint conflicts with exact readback")
        if git_blob_sha1(remote_verified)!=current_map[verified_relative]["sha"]:
            raise SystemExit("Q92_PERSIST_BLOCKED: existing verified checkpoint Git blob SHA1 mismatch")
        final_sha=head
    else:
        verified_extra={"readback_status":"PERSISTED_READBACK_VERIFIED","persisted_output_commit_sha":first_commit,
            "verified_file_count":file_count,"verified_bytes":total_bytes,"verified_tree_sha":readback_tree_sha,
            "all_output_bytes_exact":True,"human_review_integration_pending":True}
        verified_checkpoint=make_checkpoint(report,run_id,attempt,first_commit,"PERSISTED_READBACK_VERIFIED_PENDING_HUMAN_REVIEW",verified_extra)
        verified_bytes=json.dumps(verified_checkpoint,ensure_ascii=False,indent=2).encode("utf-8")+b"\n"
        verified_blob=create_blob(verified_bytes)
        verified_element={"path":verified_relative,"mode":"100644","type":"blob","sha":verified_blob}
        current_commit=api("GET","/git/commits/"+first_commit)
        current_tree_sha=current_commit["tree"]["sha"]
        final_tree,_=create_tree_chunked(current_tree_sha,[verified_element],TREE_CHUNK_SIZE)
        checkpoint_commit=api("POST","/git/commits",{"message":"Append Q92 exact-byte readback checkpoint [q92-readback-checkpoint]","tree":final_tree,"parents":[first_commit]})
        final_sha=checkpoint_commit["sha"]
        branch_ref=api("GET","/git/ref/heads/"+BRANCH)
        if branch_ref.get("object",{}).get("sha")!=first_commit:
            raise SystemExit("Q92_PERSIST_BLOCKED: branch head advanced before readback checkpoint ref update")
        api("PATCH","/git/refs/heads/"+BRANCH,{"sha":final_sha,"force":False})
        check_ref=api("GET","/git/ref/heads/"+BRANCH)
        if check_ref.get("object",{}).get("sha")!=final_sha:
            raise SystemExit("Q92_PERSIST_BLOCKED: readback checkpoint ref readback mismatch")
        remote_verified=blob_bytes(verified_blob)
        if remote_verified!=verified_bytes or sha256(remote_verified)!=sha256(verified_bytes) or git_blob_sha1(remote_verified)!=verified_blob:
            raise SystemExit("Q92_PERSIST_BLOCKED: verified checkpoint exact-byte readback mismatch")
        created_commit=True
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as handle:
            handle.write("commit_created="+("true" if created_commit else "false")+"\ncommit_sha="+final_sha+"\n")
    print(json.dumps({"task_id":"Q92","persisted_head_sha":final_sha,"source_checkout_head_sha":head,
        "output_commit_sha":first_commit,"verified_checkpoint_path":verified_relative,"verified_file_count":file_count,
        "verified_bytes":total_bytes,"all_exact_commit_bytes_verified":True,"commit_created":created_commit,
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","status":"VALIDATED_PENDING_HUMAN_REVIEW"},separators=(",",":")))

if __name__=="__main__":
    main()
