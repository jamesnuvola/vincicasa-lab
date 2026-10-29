#!/usr/bin/env python3
"""Chunk Q86 metrics into checksum-registered gzip parts for safe Git persistence."""
from __future__ import annotations
import csv, gzip, hashlib, io, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
REPORT=OUT/"per_number_condition_6plus_grammar.json"
METRICS=OUT/"per_number_condition_6plus_formula_metrics.csv"
MANIFEST=OUT/"per_number_condition_6plus_formula_metrics_manifest.json"
CHUNK_ROWS=30000
def sha256(data): return hashlib.sha256(data).hexdigest()
def write_gzip_csv(path,fields,rows):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as text:
                writer=csv.DictWriter(text,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
def main():
    if not METRICS.is_file(): raise SystemExit("Q86_CHUNK_BLOCKED: monolithic metrics CSV missing")
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    parts=[]; total=0; part_index=0
    with METRICS.open(newline="",encoding="utf-8-sig") as source:
        reader=csv.DictReader(source); fields=reader.fieldnames
        if not fields: raise SystemExit("Q86_CHUNK_BLOCKED: metrics header missing")
        rows=[]
        for row in reader:
            rows.append(row)
            if len(rows)==CHUNK_ROWS:
                rel=f"reports/sequence_agent/per_number_condition_6plus_formula_metrics_part_{part_index:02d}.csv.gz"
                path=ROOT/rel; write_gzip_csv(path,fields,rows); data=path.read_bytes()
                parts.append({"part_index":part_index,"path":rel,"rows":len(rows),"row_start_inclusive":total,
                    "row_end_exclusive":total+len(rows),"bytes":len(data),"sha256":sha256(data)})
                total+=len(rows); part_index+=1; rows=[]
        if rows:
            rel=f"reports/sequence_agent/per_number_condition_6plus_formula_metrics_part_{part_index:02d}.csv.gz"
            path=ROOT/rel; write_gzip_csv(path,fields,rows); data=path.read_bytes()
            parts.append({"part_index":part_index,"path":rel,"rows":len(rows),"row_start_inclusive":total,
                "row_end_exclusive":total+len(rows),"bytes":len(data),"sha256":sha256(data)})
            total+=len(rows); part_index+=1
    expected=int(report.get("metrics_rows",-1))
    if total!=expected or total!=int(report.get("formula_count",0))*3:
        raise SystemExit(f"Q86_CHUNK_BLOCKED: chunk rows {total} do not match report {expected}")
    if part_index!=(expected+CHUNK_ROWS-1)//CHUNK_ROWS: raise SystemExit("Q86_CHUNK_BLOCKED: unexpected chunk count")
    parts_sha=sha256(json.dumps(parts,sort_keys=True,separators=(",",":")).encode("utf-8"))
    manifest={"schema_version":"1.0","task_id":"Q86","storage_format":"chunked_csv_gzip_parts",
        "source_archive_sha256":report.get("source_archive_sha256"),"formula_count":report.get("formula_count"),
        "metrics_rows":total,"part_count":len(parts),"parts_manifest_sha256":parts_sha,"parts":parts}
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report["metrics_storage"]="chunked_csv_gzip_parts"; report["metrics_parts"]=parts
    report["outputs"]["metrics"]=None
    report["outputs"]["metrics_manifest"]="reports/sequence_agent/per_number_condition_6plus_formula_metrics_manifest.json"
    report["outputs"]["metrics_parts_manifest_sha256"]=parts_sha
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    METRICS.unlink()
    print(json.dumps({"task_id":"Q86","metrics_rows":total,"part_count":len(parts),
        "parts_manifest_sha256":parts_sha,"monolithic_csv_removed":True},separators=(",",":")))
if __name__=="__main__": main()
