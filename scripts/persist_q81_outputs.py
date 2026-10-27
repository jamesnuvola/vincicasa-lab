#!/usr/bin/env python3
"""Persist validated Q80/Q81 outputs via Git Data API and dispatch exact-head CI."""
from __future__ import annotations
import json,os,subprocess,sys,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BRANCH="research/q81-higher-order-condition-grammar-20261027-current"
OUTPUTS=("reports/sequence_agent/per_number_condition_grammar.json","reports/sequence_agent/per_number_condition_formula_metrics.csv","reports/sequence_agent/per_number_condition_target_ledger.csv",
 "reports/sequence_agent/higher_order_condition_grammar.json","reports/sequence_agent/higher_order_condition_formula_metrics_discovery.csv","reports/sequence_agent/higher_order_condition_formula_metrics_validation.csv",
 "reports/sequence_agent/higher_order_condition_formula_metrics_blind_oos.csv","reports/sequence_agent/higher_order_condition_target_ledger.csv","reports/sequence_agent/research_queue_status.json")
API="https://api.github.com"
def api(method,path,payload=None):
 token=os.environ.get("GITHUB_TOKEN"); repo=os.environ.get("GITHUB_REPOSITORY")
 if not token or not repo: raise SystemExit("Q81_PERSIST_BLOCKED: missing GitHub token/repository context")
 data=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
 req=urllib.request.Request(API+"/repos/"+repo+path,data=data,method=method,headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"VinciCasa-SONAR-Q81-persistence"})
 try:
  with urllib.request.urlopen(req,timeout=300) as response: raw=response.read()
 except urllib.error.HTTPError as exc: raise SystemExit("Q81_PERSIST_BLOCKED: GitHub API "+str(exc.code)+" "+exc.read().decode("utf-8",errors="replace")[:2000]) from exc
 except Exception as exc: raise SystemExit("Q81_PERSIST_BLOCKED: GitHub API request failed: "+str(exc)) from exc
 return json.loads(raw.decode("utf-8")) if raw else {}
def head_file(path):
 r=subprocess.run(["git","show","HEAD:"+path],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL); return r.stdout if r.returncode==0 else None
def main():
 if os.environ.get("GITHUB_REF_NAME")!=BRANCH: raise SystemExit("Q81_PERSIST_BLOCKED: refusing write outside registered branch")
 head=os.environ.get("GITHUB_SHA",""); repo=os.environ.get("GITHUB_REPOSITORY","")
 if not head or not repo: raise SystemExit("Q81_PERSIST_BLOCKED: missing commit/repository context")
 sys.path.insert(0,str(ROOT/"scripts"))
 from sonar_research_queue import validate_q00,validate_q80,validate_q81
 for label,validator in (("Q00",validate_q00),("Q80",validate_q80),("Q81",validate_q81)):
  errors=validator()
  if errors: raise SystemExit("Q81_PERSIST_BLOCKED: "+label+" acceptance failed: "+" | ".join(errors))
 queue=json.loads((ROOT/OUTPUTS[-1]).read_text(encoding="utf-8"))
 q80=next((t for t in queue.get("tasks",[]) if t.get("id")=="Q80"),None); q81=next((t for t in queue.get("tasks",[]) if t.get("id")=="Q81"),None)
 if queue.get("queue_status")!="QUEUE_VALID" or not q80 or not q81: raise SystemExit("Q81_PERSIST_BLOCKED: queue invalid or Q80/Q81 missing")
 for task in (q80,q81):
  if task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"): raise SystemExit("Q81_PERSIST_BLOCKED: task not validated/pending human review: "+str(task.get("id")))
 report=json.loads((ROOT/OUTPUTS[3]).read_text(encoding="utf-8"))
 if report.get("review_status")!="PENDING_HUMAN_REVIEW_INTEGRATION": raise SystemExit("Q81_PERSIST_BLOCKED: human-review gate missing")
 changed=[path for path in OUTPUTS if head_file(path)!=(ROOT/path).read_bytes()]; out=os.environ.get("GITHUB_OUTPUT")
 if not changed:
  if out:
   with open(out,"a",encoding="utf-8") as h: h.write("commit_created=false\nnew_sha="+head+"\n")
  print("Q81_PERSIST_NOOP: validated outputs already match branch head"); return
 ref=api("GET","/git/ref/heads/"+BRANCH)
 if ref.get("object",{}).get("sha")!=head: raise SystemExit("Q81_PERSIST_BLOCKED: branch head moved; refusing stale write")
 commit_data=api("GET","/git/commits/"+head); entries=[]
 for path in changed:
  content=(ROOT/path).read_text(encoding="utf-8"); blob=api("POST","/git/blobs",{"content":content,"encoding":"utf-8"})
  entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]}); print("Q81_PERSIST_BLOB: "+path+" chars="+str(len(content)))
 tree=api("POST","/git/trees",{"base_tree":commit_data["tree"]["sha"],"tree":entries})
 commit=api("POST","/git/commits",{"message":"Persist validated Q80/Q81 higher-order research outputs","tree":tree["sha"],"parents":[head]})
 api("PATCH","/git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False})
 if out:
  with open(out,"a",encoding="utf-8") as h: h.write("commit_created=true\nnew_sha="+commit["sha"]+"\n")
 print("Q81_PERSIST_COMMIT: "+commit["sha"])
 api("POST","/actions/workflows/ci.yml/dispatches",{"ref":BRANCH})
 print("Q81_PERSIST_EXACT_HEAD_CI_DISPATCHED: "+commit["sha"])
if __name__=="__main__": main()
