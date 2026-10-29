#!/usr/bin/env python3
"""Persist validated Q86 outputs through Git Data API and verify exact committed bytes."""
from __future__ import annotations
import base64, hashlib, json, os, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
BRANCH="research/per-number-condition-grammar-20261026"
API="https://api.github.com"
def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN"); repo=os.environ.get("GITHUB_REPOSITORY","jamesnuvola/vincicasa-lab")
    if not token: raise SystemExit("Q86_PERSIST_BLOCKED: missing GITHUB_TOKEN")
    data=None if payload is None else json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    req=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={
        "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q86-persistence"})
    try:
        with urllib.request.urlopen(req,timeout=300) as response: raw=response.read()
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode("utf-8",errors="replace")[:2000]
        raise SystemExit("Q86_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+detail) from exc
    return json.loads(raw.decode()) if raw else {}
def sha256(data): return hashlib.sha256(data).hexdigest()
def main():
    report=json.loads((OUT/"per_number_condition_6plus_grammar.json").read_text(encoding="utf-8"))
    if report.get("task_id")!="Q86" or report.get("status")!="VALIDATED_FINITE_GRAMMAR_COMPLETE":
        raise SystemExit("Q86_PERSIST_BLOCKED: Q86 report not validated")
    paths=["reports/sequence_agent/per_number_condition_6plus_grammar.json",
        "reports/sequence_agent/per_number_condition_6plus_formula_metrics_manifest.json",
        "reports/sequence_agent/per_number_condition_6plus_target_ledger.csv",
        "reports/sequence_agent/research_queue_status.json",
        "reports/sequence_agent/per_number_condition_research_checkpoint.json"]
    paths.extend(str(p["path"]) for p in report.get("metrics_parts",[]))
    payloads={}
    for rel in paths:
        path=ROOT/rel
        if not path.is_file(): raise SystemExit("Q86_PERSIST_BLOCKED: missing output "+rel)
        payloads[rel]=path.read_bytes()
    parent=api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]
    base_tree=api("GET","/git/commits/"+parent)["tree"]["sha"]
    elements=[]; expected={}
    for rel,data in payloads.items():
        blob=api("POST","/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
        elements.append({"path":rel,"mode":"100644","type":"blob","sha":blob["sha"]})
        expected[rel]={"blob_sha":blob["sha"],"bytes":len(data),"sha256":sha256(data)}
    tree=api("POST","/git/trees",{"base_tree":base_tree,"tree":elements})
    commit=api("POST","/git/commits",{"message":"Persist validated Q86 six-feature formula results and checkpoint [q80-validate-persisted] [q86-persisted]","tree":tree["sha"],"parents":[parent]})
    if api("GET","/git/ref/heads/"+BRANCH)["object"]["sha"]!=parent:
        raise SystemExit("Q86_PERSIST_BLOCKED: branch advanced during persistence; refusing ref update")
    api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
    committed=api("GET","/git/commits/"+commit["sha"])
    tree_doc=api("GET","/git/trees/"+committed["tree"]["sha"]+"?recursive=1")
    tree_map={x["path"]:x for x in tree_doc.get("tree",[]) if x.get("type")=="blob"}
    for rel,data in payloads.items():
        entry=tree_map.get(rel)
        if not entry or entry.get("sha")!=expected[rel]["blob_sha"] or int(entry.get("size",-1))!=len(data):
            raise SystemExit("Q86_PERSIST_BLOCKED: exact-commit tree mismatch for "+rel)
        blob=api("GET","/git/blobs/"+entry["sha"]); reread=base64.b64decode(blob["content"])
        if reread!=data or sha256(reread)!=expected[rel]["sha256"]:
            raise SystemExit("Q86_PERSIST_BLOCKED: exact-byte reread mismatch for "+rel)
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as handle:
            handle.write("commit_created=true\n"); handle.write("commit_sha="+commit["sha"]+"\n")
    print(json.dumps({"task_id":"Q86","persisted_head_sha":commit["sha"],"parent_sha":parent,
        "verified_file_count":len(payloads),"verified_bytes":sum(len(v) for v in payloads.values()),
        "all_exact_commit_bytes_verified":True,"review_status":"PENDING_HUMAN_REVIEW_INTEGRATION"},separators=(",",":")))
if __name__=="__main__": main()
