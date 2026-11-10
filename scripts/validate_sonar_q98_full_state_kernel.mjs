"use strict";
const fs=require("node:fs");
const report=JSON.parse(fs.readFileSync("reports/sequence_agent/q98_full_state_kernel_report_2026-11-10.json","utf8"));
const source=fs.readFileSync("data/storico_daily.csv","utf8").trimEnd().split(/\r?\n/).slice(1).map(l=>{const a=l.split(",");return {date:a[0],nums:a.slice(1).map(Number)};});
const lines=fs.readFileSync("reports/sequence_agent/q98_full_state_kernel_target_ledger_2026-11-10.csv","utf8").trimEnd().split(/\r?\n/);
function ok(x,m){if(!x)throw new Error(m);}
ok(report.experiment_id==="SONAR-Q98-LAG1-FULL-DRAW-GEOMETRY-KERNEL-2026-11-10","wrong experiment id");
ok(report.source.draws===3403 && report.source.last_date==="2026-11-09","source cutoff mismatch");
ok(report.source.target_count===3103 && lines.length===3104,"ledger row count mismatch");
ok(report.splits.discovery===1400 && report.splits.validation===850 && report.splits.blind_oos_historical===853,"split counts mismatch");
ok(report.integrity.strict_prior_cutoff_checks===3103 && report.integrity.all_training_outcomes_strictly_before_target,"strict-prior audit failed");
ok(report.integrity.missing_targets===0 && report.integrity.all_draws_valid_sorted_5_of_40,"archive integrity failed");
ok(report.integrity.synthetic_tests.passed===5,"synthetic tests failed");
ok(report.blind_inference.family_size===8 && report.blind_inference.tests.length===8,"Holm family mismatch");
ok(report.decision.promotion_allowed===false && report.decision.merge_allowed===false,"unsafe decision flags");
const header=lines[0].split(",");
ok(header[0]==="target_date" && header[1]==="history_cutoff","ledger header mismatch");
for(let i=1;i<lines.length;i++){
 const a=lines[i].split(","), t=300+i-1, expected=source[t], previous=source[t-1];
 const split=i-1<1400?"discovery":i-1<2250?"validation":"blind_oos_historical";
 ok(a.length===header.length,"ledger column count mismatch at row "+i);
 ok(expected && a[0]===expected.date && a[1]===previous.date,"target/cutoff does not match canonical archive at row "+i);
 ok(Number(a[3])===t && Number(a[4])===t-1,"strict-prior index mismatch at row "+i);
 ok(a[5]===previous.nums.join(" ") && a[2]===split,"prior state or chronological split mismatch at row "+i);
 ok(a[0]>a[1],"target date must follow history cutoff at row "+i);
 for(const k of [6,7,8,9,10,16,17,18])ok(Number.isFinite(Number(a[k])),"nonfinite metric at row "+i);
}
ok(report.integrity.max_probability_sum_error<1e-10,"probability normalization tolerance exceeded");
for(const t of report.blind_inference.tests){ok(t.holm_adjusted_p>=t.block_signflip_p_one_sided && t.holm_adjusted_p<=1,"Holm adjusted p-value invalid for "+t.id);}
console.log(JSON.stringify({status:"Q98_INDEPENDENT_REPORT_LEDGER_VALIDATION_PASS",ledger_rows:lines.length-1,columns:header.length,blind_tests:report.blind_inference.family_size,canonical_cutoff_reconciliation:"PASS"}));
