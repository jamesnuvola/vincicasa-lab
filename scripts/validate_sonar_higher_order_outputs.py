#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from sonar_research_queue import load_json,validate_q81
errors=validate_q81()
if errors: print("Q81_ACCEPTANCE_BLOCKED: "+" | ".join(errors)); raise SystemExit(1)
queue=load_json(ROOT/"reports"/"sequence_agent"/"research_queue_status.json")
task=next((t for t in queue.get("tasks",[]) if t.get("id")=="Q81"),None)
if queue.get("queue_status")!="QUEUE_VALID" or not task: raise SystemExit("Q81_ACCEPTANCE_BLOCKED: queue/task missing or invalid")
if task.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or task.get("validation_errors"): raise SystemExit("Q81_ACCEPTANCE_BLOCKED: Q81 not validated/pending human review")
print("Q81_ACCEPTANCE_VALIDATED_PENDING_HUMAN_REVIEW")
