#!/usr/bin/env python3
"""Persist the accepted Q90 bundle append-only and verify exact Git blob readback."""
from __future__ import annotations
import base64,hashlib,json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path

REPO=os.environ["GITHUB_REPOSITORY"]
BRANCH=os.environ.get("GITHUB_REF_NAME","research/q90-edge-field-decomposition-20261110")
TOKEN=os.environ["GITHUB_TOKEN"]
API="https://api.github.com"
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/".q90-bundle"
PREFIX="reports/sequence_agent/"
NAMES=("q90_edge_field_decomposition_catalog.jsonl",
       "q90_edge_field_decomposition_target_ledger.csv.gz",
       "q90_edge_field_decomposition_report.json",
       "q90_edge_field_decomposition_manifest.json",
       "q90_edge_field_decomposition_checkpoint_2026-11-10.md",
       "q90_edge_field_decomposition_validation.json")

def api(method,path,payload=None):
    data=None if payload is None else json.dumps(payload,separators=(",",":")).encode()
    req=urllib.request.Request(API+path,data=data,method=method,headers={
      "Accept":"application/vnd.github+json","Authorization":"Bearer "+TOKEN,
      "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=120) as response:
            raw=response.read()
            return json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as exc:
        body=exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed {exc.code}: {body[:2000]}") from exc

def sha256(data): return hashlib.sha256(data).hexdigest()

def main():
    files={name:(BUNDLE/name).read_bytes() for name in NAMES}
    manifest=json.loads(files["q90_edge_field_decomposition_manifest.json"])
    validation=json.loads(files["q90_edge_field_decomposition_validation.json"])
    if validation.get("status")!="PASS" or manifest.get("status")!="ACCEPTANCE_PASS":
        raise SystemExit("Q90 persistence blocked: independent acceptance is not PASS")
    if validation.get("task_id")!="Q90-EDGE-FIELD-DECOMPOSITION-01":
        raise SystemExit("Q90 persistence blocked: validation task identity mismatch")
    for key,name in (("catalog",NAMES[0]),("target_ledger",NAMES[1]),("report",NAMES[2]),
                     ("checkpoint",NAMES[4]),("validation",NAMES[5])):
        meta=manifest["files"].get(key)
        if not meta or meta["bytes"]!=len(files[name]) or meta["sha256"]!=sha256(files[name]):
            raise SystemExit("Q90 persistence blocked: artifact/manifest mismatch for "+key)
    ref_get="/repos/"+REPO+"/git/ref/heads/"+urllib.parse.quote(BRANCH,safe="/")
    ref_patch="/repos/"+REPO+"/git/refs/heads/"+urllib.parse.quote(BRANCH,safe="/")
    ref=api("GET",ref_get); parent=ref["object"]["sha"]
    parent_commit=api("GET","/repos/"+REPO+"/git/commits/"+parent)
    base_tree=parent_commit["tree"]["sha"]
    entries=[]; blob_map={}
    for name,data in files.items():
        path=PREFIX+name
        try:
            api("GET","/repos/"+REPO+"/contents/"+urllib.parse.quote(path,safe="/")+"?ref="+urllib.parse.quote(BRANCH,safe="/"))
        except RuntimeError as exc:
            if "failed 404" not in str(exc): raise
        else:
            raise SystemExit("Q90 append-only persistence blocked; path already exists: "+path)
        blob=api("POST","/repos/"+REPO+"/git/blobs",{"content":base64.b64encode(data).decode("ascii"),"encoding":"base64"})
        entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]})
        blob_map[path]={"sha":blob["sha"],"bytes":len(data),"sha256":sha256(data)}
    tree=api("POST","/repos/"+REPO+"/git/trees",{"base_tree":base_tree,"tree":entries})
    commit=api("POST","/repos/"+REPO+"/git/commits",{
      "message":"Persist Q90 accepted edge-field decomposition outputs [q90-results-persisted]",
      "tree":tree["sha"],"parents":[parent]})
    api("PATCH",ref_patch,{"sha":commit["sha"],"force":False})
    final_ref=api("GET",ref_get)
    if final_ref["object"]["sha"]!=commit["sha"]:
        raise SystemExit("Q90 persistence blocked: branch head differs from created commit")
    for path,meta in blob_map.items():
        blob=api("GET","/repos/"+REPO+"/git/blobs/"+meta["sha"])
        if blob.get("encoding")!="base64": raise SystemExit("Q90 unexpected blob encoding: "+path)
        readback=base64.b64decode(blob["content"])
        if len(readback)!=meta["bytes"] or sha256(readback)!=meta["sha256"]:
            raise SystemExit("Q90 exact-byte readback mismatch: "+path)
    result={"status":"PERSISTED_AND_READBACK_VERIFIED","parent_sha":parent,"persisted_head":commit["sha"],
            "files":blob_map,"acceptance":"PASS","predictive_gate":validation.get("primary_gate",{}).get("status")}
    print("SONAR_Q90_PERSISTENCE_BEGIN")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    print("SONAR_Q90_PERSISTENCE_END")
    out=os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out,"a",encoding="utf-8") as handle: handle.write("commit_sha="+commit["sha"]+"\n")

if __name__=="__main__": main()
