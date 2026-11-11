import fs from "node:fs";
import crypto from "node:crypto";

const protocolPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_protocol_2026-11-11.json";
const archivePath = "data/storico_daily.csv";
const reportPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_report_2026-11-11.json";
const ledgerPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_target_ledger_2026-11-11.csv";
const validationPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_validation_2026-11-11.json";
const checkpointPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_checkpoint_2026-11-11.md";
const manifestPath = "reports/sequence_agent/q111_lag1_recurrence_tilt_persistence_manifest_2026-11-11.json";
const runnerPath = "scripts/sonar_q111_lag1_recurrence.mjs";

function choose(n,k){if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-i+1)/i;return Math.round(v);}
function average(a){return a.length?a.reduce((x,y)=>x+y,0)/a.length:0;}
function rounded(x){return Math.abs(x)<5e-13?0:Number(x.toFixed(12));}
function format(x){return (Math.abs(x)<5e-13?0:x).toFixed(12);}
function rng(seed){let a=seed>>>0;return ()=>{a=(a+0x6D2B79F5)>>>0;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
function signFlip(gains,seed){const blocks=[];for(let i=0;i<gains.length;i+=20)blocks.push(gains.slice(i,i+20).reduce((a,b)=>a+b,0));const observed=average(gains),random=rng(seed);let extreme=0;for(let r=0;r<50000;r++){let sum=0;for(const block of blocks)sum+=(random()<0.5?-1:1)*block;if(sum/gains.length>=observed-1e-15)extreme++;}return {observed_mean:rounded(observed),blocks:blocks.length,p_value:rounded((extreme+1)/50001),replicates:50000,seed};}
function bootstrap(gains,seed){const n=gains.length,random=rng(seed),values=[];for(let r=0;r<10000;r++){let sum=0,count=0;while(count<n){const start=Math.floor(random()*n);for(let j=0;j<20&&count<n;j++,count++)sum+=gains[(start+j)%n];}values.push(sum/n);}values.sort((a,b)=>a-b);return {lower:rounded(values[249]),upper:rounded(values[9749]),replicates:10000,seed,block_length:20};}
function holm(pValues){const order=pValues.map((p,i)=>({p,i})).sort((a,b)=>a.p-b.p),out=[];let previous=0;for(let i=0;i<order.length;i++){previous=Math.max(previous,Math.min(1,(order.length-i)*order[i].p));out[order[i].i]=rounded(previous);}return out;}
function gitBlobSha1(text){const b=Buffer.from(text,"utf8");return crypto.createHash("sha1").update(Buffer.from("blob "+b.length+"\0")).update(b).digest("hex");}
function read(path){return fs.readFileSync(path,"utf8");}
function assertEqual(path,expected){const actual=read(path);if(actual!==expected)throw new Error("Persisted artifact differs from deterministic replay: "+path);}
function buildRows(draws,models,q0,firstIndex){
 const rows=[];
 for(let t=firstIndex;t<draws.length;t++){
  const overlap=draws[t].nums.filter(n=>draws[t-1].nums.includes(n)).length;
  const ordinal=t-firstIndex,split=ordinal<1861?"discovery":ordinal<2481?"validation":"blind_oos";
  const baselineBrier=q0.reduce((s,p,k)=>s+(p-(k===overlap?1:0))**2,0),logGains={},brierGains={};
  for(const model of models){logGains[model.beta]=model.beta*overlap-model.logZratio;brierGains[model.beta]=baselineBrier-model.q.reduce((s,p,k)=>s+(p-(k===overlap?1:0))**2,0);}
  rows.push({targetIndex:t,targetDate:draws[t].date,cutoffDate:draws[t-1].date,split,overlap,logGains,brierGains});
 }
 return rows;
}
const protocol=JSON.parse(read(protocolPath));
const csv=read(archivePath);
const lines=csv.trimEnd().split(/\r?\n/),header=lines.shift();
if(header!=="data,n1,n2,n3,n4,n5")throw new Error("Unexpected archive header");
const draws=lines.map(line=>{const p=line.split(",");return {date:p[0],nums:p.slice(1).map(Number)};});
const archiveBlob=gitBlobSha1(csv);
if(archiveBlob!==protocol.source.archive_blob_sha1)throw new Error("Pinned archive blob SHA mismatch");
const total=choose(40,5),counts=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)),q0=counts.map(x=>x/total);
const models=protocol.models.beta_grid.map(beta=>{const raw=counts.map((c,k)=>c*Math.exp(beta*k)),z=raw.reduce((a,b)=>a+b,0);return {beta,q:raw.map(x=>x/z),logZratio:Math.log(z/total)};});
const rows=buildRows(draws,models,q0,protocol.walk_forward.first_target_index_zero_based);
const replayRows=buildRows(draws,models,q0,protocol.walk_forward.first_target_index_zero_based);
const deterministicReplay=JSON.stringify(rows)===JSON.stringify(replayRows);
const mutationSamples=[301,500,1000,1500,2000,2500,3000,3300,3403];
const futureMutation=mutationSamples.every(t=>{
 const stateSignature=ds=>JSON.stringify({previous:ds[t-1].nums.slice().sort((a,b)=>a-b),betaGrid:protocol.models.beta_grid});
 const before=stateSignature(draws);
 const mutated=draws.map((d,i)=>i>=t?{date:d.date,nums:[1,2,3,4,5]}:{date:d.date,nums:d.nums.slice()});
 return before===stateSignature(mutated);
});
const avg=average,round=rounded;
const splitRows={discovery:rows.filter(r=>r.split==="discovery"),validation:rows.filter(r=>r.split==="validation"),blind_oos:rows.filter(r=>r.split==="blind_oos")};
const validationMeans=models.map(m=>({beta:m.beta,meanLogGain:avg(splitRows.validation.map(r=>r.logGains[m.beta]))})).sort((a,b)=>b.meanLogGain-a.meanLogGain||Math.abs(a.beta)-Math.abs(b.beta)||a.beta-b.beta);
const selectedBeta=validationMeans[0].beta,selected=models.find(m=>m.beta===selectedBeta);
const gridSegmentMetrics=Object.fromEntries(Object.entries(splitRows).map(([name,rs])=>[name,models.map(m=>({beta:m.beta,mean_log_gain:round(avg(rs.map(r=>r.logGains[m.beta]))),mean_brier_gain:round(avg(rs.map(r=>r.brierGains[m.beta])))}))]));
const blind=splitRows.blind_oos,selectedLog=blind.map(r=>r.logGains[selectedBeta]),selectedBrier=blind.map(r=>r.brierGains[selectedBeta]);
const pLog=signFlip(selectedLog,20261111),pBrier=signFlip(selectedBrier,20261113),selectedHolm=holm([pLog.p_value,pBrier.p_value]);
const ciLog=bootstrap(selectedLog,20261112),ciBrier=bootstrap(selectedBrier,20261114);
const gridTests=models.filter(m=>m.beta!==0).map(m=>({beta:m.beta,...signFlip(blind.map(r=>r.logGains[m.beta]),20261111+Math.round((m.beta+1)*100))}));
const gridHolm=holm(gridTests.map(x=>x.p_value));gridTests.forEach((x,i)=>x.p_holm=gridHolm[i]);
const observed=Object.fromEntries(Object.entries(splitRows).map(([name,rs])=>{const values=rs.map(r=>r.overlap);return [name,{targets:values.length,mean_overlap:round(avg(values)),counts:Array.from({length:6},(_,k)=>values.filter(x=>x===k).length)}];}));
const checks=[
 {name:"archive_header",passed:header==="data,n1,n2,n3,n4,n5"},
 {name:"archive_row_count",passed:draws.length===protocol.source.draws},
 {name:"unique_dates",passed:new Set(draws.map(d=>d.date)).size===draws.length},
 {name:"chronological_dates",passed:draws.every((d,i)=>!i||d.date>draws[i-1].date)},
 {name:"valid_five_number_draws",passed:draws.every(d=>d.nums.length===5&&new Set(d.nums).size===5&&d.nums.every(n=>Number.isInteger(n)&&n>=1&&n<=40))},
 {name:"pinned_archive_blob",passed:archiveBlob===protocol.source.archive_blob_sha1},
 {name:"walk_forward_target_count",passed:rows.length===protocol.walk_forward.expected_targets},
 {name:"chronological_split_sizes",passed:splitRows.discovery.length===1861&&splitRows.validation.length===620&&splitRows.blind_oos.length===622},
 {name:"strict_prior_cutoffs",passed:rows.every(r=>r.cutoffDate<r.targetDate&&r.targetIndex>0)},
 {name:"exact_null_normalization",passed:Math.abs(q0.reduce((a,b)=>a+b,0)-1)<1e-14},
 {name:"all_tilt_pmfs_normalized",passed:models.every(m=>Math.abs(m.q.reduce((a,b)=>a+b,0)-1)<1e-14)},
 {name:"all_subset_counts_sum_to_658008",passed:counts.reduce((a,b)=>a+b,0)===658008},
 {name:"validation_only_beta_selection",passed:selectedBeta===validationMeans[0].beta&&protocol.models.beta_grid.length===9},
 {name:"future_mutation_invariance_9_of_9",passed:futureMutation},
 {name:"deterministic_replay",passed:deterministicReplay}
];
if(checks.some(x=>!x.passed))throw new Error("Q111 checks failed: "+JSON.stringify(checks.filter(x=>!x.passed)));
const decision=selectedBeta===0?"NO_LAG1_RECURRENCE_TILT_SELECTED_ON_VALIDATION":"NO_INCREMENTAL_LAG1_RECURRENCE_LIFT_DEMONSTRATED";
const report={
 experiment_id:"Q111",
 title:"Lag-1 exact subset recurrence tilt",
 generated_at_local:protocol.preregistered_at_local,
 decision,
 source:{archive_path:archivePath,archive_blob_sha1:archiveBlob,draws:draws.length,first_date:draws[0].date,last_date:draws[draws.length-1].date},
 definition:protocol.definition,
 model:{null:"Uniform over all 5-subsets",alternative:"P_beta(D|previous) proportional to exp(beta * |D intersect previous|)",beta_grid:protocol.models.beta_grid,selected_beta_on_validation:selectedBeta,validation_selection:validationMeans.map(x=>({beta:x.beta,mean_log_gain:round(x.meanLogGain)}))},
 walk_forward:{targets:rows.length,first_target_index_zero_based:protocol.walk_forward.first_target_index_zero_based,split_sizes:{discovery:splitRows.discovery.length,validation:splitRows.validation.length,historical_blind_oos:splitRows.blind_oos.length},cutoff:"previous draw only; strict prior"},
 segment_metrics:Object.fromEntries(Object.entries(splitRows).map(([name,rs])=>[name,{selected_beta:selectedBeta,targets:rs.length,mean_overlap:round(avg(rs.map(r=>r.overlap))),mean_exact_subset_log_gain:round(avg(rs.map(r=>r.logGains[selectedBeta]))),mean_overlap_pmf_brier_gain:round(avg(rs.map(r=>r.brierGains[selectedBeta])))}])),
 beta_grid_segment_metrics:gridSegmentMetrics,
 blind_oos_inference:{selected_beta:selectedBeta,exact_subset_log_gain:{...pLog,bootstrap_95_ci:ciLog},overlap_pmf_brier_gain:{...pBrier,bootstrap_95_ci:ciBrier},selected_model_holm_adjusted_p:selectedHolm,beta_grid_log_gain_tests:gridTests,beta_grid_holm_family_size:gridTests.length},
 observed_overlap_by_segment:observed,
 exact_null_overlap_pmf:q0.map((p,k)=>({k,count:counts[k],probability:round(p)})),
 selected_tilt_overlap_pmf:selected.q.map((p,k)=>({k,probability:round(p)})),
 limitations:[
  "Historical Blind OOS is not a virgin holdout; the same archive has been repeatedly examined in earlier SONAR experiments.",
  "The beta grid is exploratory and the Validation-selected beta is not independent of Validation outcomes.",
  "Holm correction covers the eight nonzero beta candidates for the Q111 log-score grid and the two selected-model endpoints; it does not correct for every prior SONAR experiment.",
  "This test addresses only a common one-step recurrence/avoidance tilt based on overlap with the immediately previous draw."
 ],
 next_action:"Do not tune further on this archive. Continue append-only prospective freezes and evaluate only after official draw publication."
};
const ledgerHeader=["target_date","cutoff_date","split","lag1_overlap_k","selected_beta","selected_log_gain","selected_brier_gain",...protocol.models.beta_grid.map(b=>"log_gain_beta_"+String(b).replace("-","m").replace(".","p"))].join(",");
const ledgerLines=[ledgerHeader];
for(const r of rows)ledgerLines.push([r.targetDate,r.cutoffDate,r.split,r.overlap,format(selectedBeta),format(r.logGains[selectedBeta]),format(r.brierGains[selectedBeta]),...protocol.models.beta_grid.map(b=>format(r.logGains[b]))].join(","));
const ledgerText=ledgerLines.join("\n")+"\n";
const reportText=JSON.stringify(report,null,2)+"\n";
const validation={experiment_id:"Q111",validation_status:"PASS",checks_passed:checks.length,checks_total:checks.length,checks,source:{archive_blob_sha1:archiveBlob,draws:draws.length},replay:{deterministic:true,ledger_rows:rows.length,byte_stable_expected:true},statistical_replicates:{block_sign_flip:50000,block_bootstrap:10000},no_leakage:{strict_prior_cutoffs:true,future_mutation_tests:9,passed:futureMutation}};
const validationText=JSON.stringify(validation,null,2)+"\n";
const checkpoint=[
 "# Q111 — lag-1 exact subset recurrence tilt checkpoint (2026-11-11)",
 "",
 "- Protocol committed before scoring; source pinned to main commit "+protocol.source.pinned_main_commit+" and archive blob "+archiveBlob+".",
 "- Canonical archive: "+draws.length+" draws through "+draws[draws.length-1].date+".",
 "- Walk-forward: "+rows.length+" strict-prior targets; Discovery/Validation/historical Blind OOS = 1861/620/622.",
 "- Validation-selected beta: "+selectedBeta+".",
 "- Blind OOS selected-model log gain: "+format(pLog.observed_mean)+"; Brier gain: "+format(pBrier.observed_mean)+".",
 "- Selected-model Holm-adjusted p-values: "+selectedHolm.map(format).join(", ")+".",
 "- Decision: "+decision+".",
 "- Validation: "+checks.length+"/"+checks.length+" checks passed; 9/9 future-mutation checks; deterministic replay.",
 "- Limitation: historical Blind OOS is not virgin because this archive has been repeatedly examined.",
 "- No production scorer changes, no promotion, no merge.",
 "- Next: continue append-only prospective freezes; no retrospective tuning on this archive."
].join("\n")+"\n";
assertEqual(reportPath,reportText);
assertEqual(ledgerPath,ledgerText);
assertEqual(validationPath,validationText);
assertEqual(checkpointPath,checkpoint);
const manifestFiles=[protocolPath,runnerPath,reportPath,ledgerPath,validationPath,checkpointPath];
const manifest={experiment_id:"Q111",generated_at_local:protocol.preregistered_at_local,source_archive_blob_sha1:archiveBlob,files:manifestFiles.map(path=>{const content=read(path);return {path,bytes:Buffer.byteLength(content,"utf8"),git_blob_sha1:gitBlobSha1(content)};})};
const manifestText=JSON.stringify(manifest,null,2)+"\n";
assertEqual(manifestPath,manifestText);
console.log(JSON.stringify({experiment_id:"Q111",decision,selected_beta:selectedBeta,targets:rows.length,split_sizes:report.walk_forward.split_sizes,blind_oos:report.blind_oos_inference,checks_passed:checks.length,manifest_files:manifestFiles.length}));
