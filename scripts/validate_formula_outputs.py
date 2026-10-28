#!/usr/bin/env python3
"""Fail-closed acceptance validation for persisted Q80 and Q81 formula outputs."""
from __future__ import annotations
import json,os,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from sonar_research_queue import validate_q80,validate_q81
REPORT80=ROOT/"reports/sequence_agent/per_number_condition_grammar.json"
REPORT81=ROOT/"reports/sequence_agent/per_number_condition_4plus_grammar.json"
QUEUE=ROOT/"reports/sequence_agent/research_queue_status.json"
CHECKPOINT=ROOT/"reports/sequence_agent/per_number_condition_research_checkpoint.json"

def main():
    errors=validate_q80()+validate_q81()
    queue=json.loads(QUEUE.read_text(encoding="utf-8"))
    q80=next((x for x in queue.get("tasks",[]) if x.get("id")=="Q80"),None)
    q81=next((x for x in queue.get("tasks",[]) if x.get("id")=="Q81"),None)
    if queue.get("queue_status")!="QUEUE_VALID": errors.append("research queue is not QUEUE_VALID")
    if not q80 or q80.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or q80.get("validation_errors"):
        errors.append("Q80 is not validated/pending human review")
    if not q81 or q81.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or q81.get("validation_errors"):
        errors.append("Q81 is not validated/pending human review")
    if errors: raise SystemExit("Q80_Q81_ACCEPTANCE_BLOCKED: "+"; ".join(errors))
    event=os.environ.get("GITHUB_EVENT_NAME","")
    # Exact-head workflow_dispatch validates persisted outputs without creating a dispatch loop.
    if event!="workflow_dispatch":
        now=datetime.now(timezone.utc).isoformat()
        run_id=os.environ.get("GITHUB_RUN_ID","local"); head=os.environ.get("GITHUB_SHA","local")
        cp=json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.is_file() else {}
        milestones={item["id"]:item for item in cp.get("verified_milestones",[])}
        for task_id,path in (("Q80",REPORT80),("Q81",REPORT81)):
            report=json.loads(path.read_text(encoding="utf-8"))
            item=milestones.get(task_id,{"id":task_id,"first_verified_at_utc":now})
            item.update({"status":"VALIDATED_PENDING_HUMAN_REVIEW","archive_cutoff":report.get("last_date"),
                "target_count":report.get("target_count"),"scored_targets":report.get("scored_targets"),
                "feature_count":report.get("feature_count"),"formula_count":report.get("formula_count"),
                "metrics_rows":report.get("metrics_rows"),"target_ledger_rows":report.get("target_ledger_rows"),
                "multiple_testing":report.get("multiple_testing"),"review_status":report.get("review_status"),
                "last_validated_at_utc":now,"last_validation_run_id":run_id,"last_validation_head_sha":head})
            milestones[task_id]=item
        cp.update({"schema_version":"1.0","project":"VinciCasa SONAR","generated_at_utc":now,
            "verified_milestones":[milestones[k] for k in sorted(milestones)],
            "current_state":{"queue_status":queue.get("queue_status"),"overall_cycle_status":queue.get("overall_cycle_status"),
                "blocking_tasks":queue.get("blocking_tasks",[]),"q80_status":q80.get("status"),
                "q81_status":q81.get("status"),"human_review_required":True,"automatic_promotion":False},
            "next_stages":[{"id":"Q82","status":"READY","scope":"conditional thresholds, nonlinear transforms and feature interactions"},
                {"id":"Q83","status":"READY","scope":"five-plus feature subsets evaluated in bounded batches"}],
            "guardrails":["only the complete prefix strictly before each target may influence its features",
                "formula universes are exhaustive only within their declared finite grammars",
                "best-per-target formula is retrospective/descriptive and never a prospective forecast",
                "immutable target freezes are append-only and are never overwritten",
                "human review/integration is required before Q80 or Q81 can be marked COMPLETE",
                "no formula is promoted automatically"]})
        history=cp.setdefault("validation_history",[])
        if not any(str(x.get("run_id"))==str(run_id) for x in history):
            history.append({"run_id":run_id,"head_sha":head,"event_name":event,"validated_at_utc":now,"status":"PASS","tasks":["Q80","Q81"]})
        CHECKPOINT.write_text(json.dumps(cp,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Q80_Q81_ACCEPTANCE_VALIDATED: formula metrics, target cutoffs, archive reconciliation and queue gate passed")

if __name__=="__main__": main()
