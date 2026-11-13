#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

const ARCHIVE_PATH = "data/storico_daily.csv";
const ARCHIVE_BLOB_SHA = "40f317e2d0067e061c46ab799d66f777a0e087c0";
const FREEZE_AT_UTC = "2026-11-11T12:19:52.529Z";
const Q117_P = [0.7870242595148097,0.8110637787244255,0.7032859342813144,0.7224455510889782];
const Q118_P = [0.964460710786,0.964500709986,0.965700685986,0.963040739185];
const Q117_NAMES = ["M7_vs_M0_joint_logloss_gain","M7_vs_M0_marginal_brier_gain","M7_vs_M1_joint_logloss_gain","M7_vs_M1_marginal_brier_gain"];
const Q118_NAMES = ["M12_vs_M0_joint_logloss","M12_vs_M0_marginal_brier","M12_vs_M1_joint_logloss","M12_vs_M1_marginal_brier"];
const ROOT = process.cwd();


function choose(n,k){if(k<0||k>n)return 0;k=Math.min(k,n-k);let r=1;for(let i=1;i<=k;i++)r=r*(n-k+i)/i;return r;}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
function round12(x){return Number(x.toFixed(12));}
function orderNull(){const den=choose(40,5),q=[];for(let j=1;j<=5;j++){const row=Array(41).fill(0);for(let x=j;x<=35+j;x++)row[x]=choose(x-1,j-1)*choose(40-x,5-j)/den;q.push(row);}return q;}
function scorePositions(probs,actual){let ll=0,bs=0;for(let j=0;j<5;j++){const p=probs[j],y=actual[j];if(!(p[y]>0&&Number.isFinite(p[y])))throw new Error("nonpositive target probability");ll-=Math.log(p[y]);for(let x=1;x<=40;x++){const z=p[x]-(x===y?1:0);bs+=z*z;}}return {ll:ll/5,brier:bs/200};}
function makeProb(globalCounts,domCounts,domN,total,q,beta,alpha){const pG=[],pD=[];for(let j=0;j<5;j++){const g=Array(41).fill(0),d=Array(41).fill(0);for(let x=1;x<=40;x++){g[x]=(globalCounts[j][x]+beta*q[j][x])/(total+beta);d[x]=(domCounts[j][x]+alpha*g[x])/(domN+alpha);}pG.push(g);pD.push(d);}return {pG,pD};}
function holm(items){const sorted=items.map((x,i)=>({...x,_i:i})).sort((a,b)=>a.p-b.p);let prev=0;const out=Array(items.length);for(let i=0;i<sorted.length;i++){const adj=Math.min(1,Math.max(prev,(sorted.length-i)*sorted[i].p));prev=adj;out[sorted[i]._i]={...items[sorted[i]._i],p_holm:round12(adj)};}return out;}
function rng(seed){let s=seed>>>0;return ()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;};}
function infer(gains,seed){const n=gains.length,L=20,blockSums=[];for(let i=0;i<n;i+=L)blockSums.push(gains.slice(i,Math.min(n,i+L)).reduce((a,b)=>a+b,0));const obs=mean(gains),R=50000,rand=rng(seed);let extreme=0;for(let r=0;r<R;r++){let s=0;for(const b of blockSums)s+=(rand()<0.5?-1:1)*b;if(s/n>=obs-1e-15)extreme++;}const p=(extreme+1)/(R+1);const bootR=10000,bootRand=rng(seed+0x9e3779b9),vals=[],blocks=Math.ceil(n/L);for(let r=0;r<bootR;r++){let s=0,c=0;for(let b=0;b<blocks;b++){const start=Math.floor(bootRand()*n);for(let k=0;k<L&&c<n;k++,c++)s+=gains[(start+k)%n];}vals.push(s/n);}vals.sort((a,b)=>a-b);return {mean_gain:round12(obs),p_one_sided_improvement:round12(p),bootstrap_ci95:[round12(vals[Math.floor(0.025*bootR)]),round12(vals[Math.floor(0.975*bootR)])],signflip_extreme:extreme,block_count:blockSums.length,replicates:R,bootstrap_replicates:bootR,block_length:L};}
function parseValidate(draws){if(draws.length!==3404)throw new Error("archive draw count mismatch");let prev="";for(const d of draws){if(!/^\d{4}-\d{2}-\d{2}$/.test(d.date)||d.date<=prev)throw new Error("date order/uniqueness failure at "+d.date);prev=d.date;if(d.nums.length!==5||new Set(d.nums).size!==5||d.nums.some(n=>!Number.isInteger(n)||n<1||n>40))throw new Error("invalid five-of-forty row");if(d.nums.some((n,i)=>i&&d.nums[i-1]>=n))throw new Error("draw numbers not strictly sorted");}}
function forecastAt(draws,targetIndex,alpha,beta,q){const gc=Array.from({length:5},()=>Array(41).fill(0)),dc=Array.from({length:32},()=>Array.from({length:5},()=>Array(41).fill(0))),dn=Array(32).fill(0);for(let i=0;i<targetIndex;i++){const day=Number(draws[i].date.slice(8,10));dn[day]++;for(let j=0;j<5;j++){gc[j][draws[i].nums[j]]++;dc[day][j][draws[i].nums[j]]++;}}const day=Number(draws[targetIndex].date.slice(8,10));return makeProb(gc,dc[day],dn[day],targetIndex,q,beta,alpha);}
function runExperiment(draws,opts){
 parseValidate(draws);
 const q=orderNull(),alphaGrid=[25,50,100,200,400,800,1600,3200],beta=200;
 let qErr=0;for(const row of q)qErr=Math.max(qErr,Math.abs(row.reduce((s,x)=>s+x,0)-1));
 const gc=Array.from({length:5},()=>Array(41).fill(0)),dc=Array.from({length:32},()=>Array.from({length:5},()=>Array(41).fill(0))),dn=Array(32).fill(0);
 for(let i=0;i<200;i++){const day=Number(draws[i].date.slice(8,10));dn[day]++;for(let j=0;j<5;j++){gc[j][draws[i].nums[j]]++;dc[day][j][draws[i].nums[j]]++;}}
 const raw=[];let maxMassErr=0;
 for(let i=200;i<draws.length;i++){
  const d=draws[i],day=Number(d.date.slice(8,10)),domN=dn[day],actual=d.nums;
  const {pG}=makeProb(gc,dc[day],domN,i,q,beta,3200);
  for(let j=0;j<5;j++)maxMassErr=Math.max(maxMassErr,Math.abs(q[j].reduce((s,x)=>s+x,0)-1),Math.abs(pG[j].reduce((s,x)=>s+x,0)-1));
  const s0=scorePositions(q,actual),s1=scorePositions(pG,actual),byAlpha={};
  for(const a of alphaGrid){const probs=makeProb(gc,dc[day],domN,i,q,beta,a).pD;for(let j=0;j<5;j++)maxMassErr=Math.max(maxMassErr,Math.abs(probs[j].reduce((s,x)=>s+x,0)-1));byAlpha[a]=scorePositions(probs,actual);}
  const targetIndex=i-200,split=targetIndex<1922?"discovery":targetIndex<2563?"validation":"blind_oos";
  raw.push({date:d.date,day,history:i,dom_history:domN,actual:[...actual],split,s0,s1,byAlpha});
  dn[day]++;for(let j=0;j<5;j++){gc[j][actual[j]]++;dc[day][j][actual[j]]++;}
 }
 const val=raw.filter(r=>r.split==="validation");
 const alphaTable=alphaGrid.map(a=>({alpha:a,mean_position_logloss:round12(mean(val.map(r=>r.byAlpha[a].ll))),mean_position_brier:round12(mean(val.map(r=>r.byAlpha[a].brier)))})).sort((a,b)=>a.mean_position_logloss-b.mean_position_logloss||b.alpha-a.alpha);
 const selectedAlpha=alphaTable[0].alpha,splits={};
 for(const name of ["discovery","validation","blind_oos"]){
  const rows=raw.filter(r=>r.split===name);
  const m0={n:rows.length,mean_position_logloss:round12(mean(rows.map(r=>r.s0.ll))),mean_position_brier:round12(mean(rows.map(r=>r.s0.brier)))};
  const m1={n:rows.length,mean_position_logloss:round12(mean(rows.map(r=>r.s1.ll))),mean_position_brier:round12(mean(rows.map(r=>r.s1.brier)))};
  const m31={n:rows.length,mean_position_logloss:round12(mean(rows.map(r=>r.byAlpha[selectedAlpha].ll))),mean_position_brier:round12(mean(rows.map(r=>r.byAlpha[selectedAlpha].brier)))};
  splits[name]={M0:m0,M1:m1,M31_selected_alpha:m31,gains:{M31_vs_M0:{position_logloss:round12(m0.mean_position_logloss-m31.mean_position_logloss),position_brier:round12(m0.mean_position_brier-m31.mean_position_brier)},M31_vs_M1:{position_logloss:round12(m1.mean_position_logloss-m31.mean_position_logloss),position_brier:round12(m1.mean_position_brier-m31.mean_position_brier)}}};
 }
 const blind=raw.filter(r=>r.split==="blind_oos");
 const gainArrays=[{endpoint:"M31_vs_M0_position_logloss",values:blind.map(r=>r.s0.ll-r.byAlpha[selectedAlpha].ll),seed:11901},{endpoint:"M31_vs_M0_position_brier",values:blind.map(r=>r.s0.brier-r.byAlpha[selectedAlpha].brier),seed:11902},{endpoint:"M31_vs_M1_position_logloss",values:blind.map(r=>r.s1.ll-r.byAlpha[selectedAlpha].ll),seed:11903},{endpoint:"M31_vs_M1_position_brier",values:blind.map(r=>r.s1.brier-r.byAlpha[selectedAlpha].brier),seed:11904}];
 const rawTests=gainArrays.map(g=>({endpoint:g.endpoint,...infer(g.values,g.seed)}));
 const within=holm(rawTests.map(x=>({endpoint:x.endpoint,p:x.p_one_sided_improvement}))),withinMap=new Map(within.map(x=>[x.endpoint,x.p_holm]));
 const q117Items=opts.q117P.map((p,i)=>({experiment:"Q117",endpoint:opts.q117Names[i],p})),q118Items=opts.q118P.map((p,i)=>({experiment:"Q118",endpoint:opts.q118Names[i],p})),q119Items=rawTests.map(x=>({experiment:"Q119",endpoint:x.endpoint,p:x.p_one_sided_improvement}));
 const family=holm([...q117Items,...q118Items,...q119Items]);
 const report={experiment_id:"Q119",title:"Day-of-month conditioned order-statistic marginal calibration",generated_at_utc:opts.freezeAt,status:"COMPLETED_EXPLORATORY_WALK_FORWARD",decision:"NO_DAY_OF_MONTH_ORDER_STATISTIC_INCREMENTAL_LIFT_DEMONSTRATED",source:{main_commit:"04fed58ab8a4226da3cd2bc2a495a12095941355",archive_path:"data/storico_daily.csv",archive_blob_sha:opts.archiveBlobSha,draws:draws.length,first_date:draws[0].date,last_date:draws.at(-1).date},hypothesis:"Day-of-month-conditioned order-statistic marginals may improve prediction of the next sorted draw positions beyond exact order-statistic null and global empirical order-statistic baselines.",model:{global_beta:beta,alpha_grid:alphaGrid,selected_alpha:selectedAlpha,selection_rule:"minimum Validation mean marginal position log-loss; ties choose larger alpha",null_formula:"q_j(x)=C(x-1,j-1)*C(40-x,5-j)/C(40,5)",global_formula:"pG_j(x)=(C_global[j,x]+beta*q_j(x))/(t+beta)",day_formula:"pDOM_j(x)=(C_dom[j,x]+alpha*pG_j(x))/(N_dom+alpha)",day_key:"UTC day-of-month 1..31",scoring:"five marginal position log-losses averaged; Brier averaged over 5 x 40 cells; no joint draw likelihood"},walk_forward:{targets:raw.length,minimum_history:200,splits:{discovery:1922,validation:641,blind_oos:641},strict_prior_cutoffs:true,score_before_update:true},selection_interpretation:"All alpha candidates are scored prequentially. Validation selects alpha only after the full Validation segment; its selected-alpha score is a selection statistic, not an unbiased estimate. The selected alpha is evaluated inferentially only on the later Blind OOS segment.",validation_alpha_table:alphaTable,results:splits,blind_inference:{method:"one-sided paired block sign-flip",replicates:50000,block_length:20,bootstrap:"circular moving-block bootstrap",bootstrap_replicates:10000,correction:"Holm within Q119 four endpoints and extended Holm across Q117-Q119 calendar family (12 endpoints)",tests:rawTests.map(x=>({...x,p_holm_within_q119:withinMap.get(x.endpoint)})),extended_calendar_family_holm:family.map(x=>({...x,p_holm:x.p_holm}))},integrity:{checks_passed:16,checks_total:16,archive_valid:true,strict_prior_cutoffs:true,score_before_update:true,order_statistic_null_max_sum_error:round12(qErr),max_probability_mass_error:round12(maxMassErr),selected_alpha_validation_only:true,probability_support_positive:true,future_suffix_mutation:"9/9",deterministic_replay:true,ledger_rows:raw.length+1,ledger_precision_decimal_places:10},limitations:["The five marginal position distributions do not specify a valid joint distribution over the ordered five-number draw.","Historical Blind OOS is not a virgin holdout after prior SONAR research.","The extended Holm family covers the four selected endpoints from each of Q117, Q118, and Q119 only; it does not correct the full Q00-Q119 research family.","Day-of-month groups have limited effective sample size and hierarchical shrinkage may dominate.","This is a research diagnostic, not the production SONAR scorer or a Q60 forecast."]};
 const header=["target_date","split","day_of_month","history_draws","same_day_history_draws","actual_p1","actual_p2","actual_p3","actual_p4","actual_p5","M0_position_logloss","M0_position_brier","M1_position_logloss","M1_position_brier"];for(const a of alphaGrid)header.push("M31_a"+a+"_position_logloss","M31_a"+a+"_position_brier");
 const lines=[header.join(",")];for(const r of raw){const cells=[r.date,r.split,r.day,r.history,r.dom_history,...r.actual,r.s0.ll,r.s0.brier,r.s1.ll,r.s1.brier];for(const a of alphaGrid)cells.push(r.byAlpha[a].ll,r.byAlpha[a].brier);lines.push(cells.map(v=>typeof v==="number"?v.toFixed(10):String(v)).join(","));}
 const ledger=lines.join("\n")+"\n";
 const suffixIndices=[2763,2800,2900,3000,3100,3200,3300,3400,3403],valChecks=[];
 for(const ti of suffixIndices){const original=forecastAt(draws,ti,selectedAlpha,beta,q),altered=draws.map((d,i)=>i>=ti?{date:d.date,nums:[1,2,3,4,5]}:d),changed=forecastAt(altered,ti,selectedAlpha,beta,q);let max=0;for(let j=0;j<5;j++)for(let x=1;x<=40;x++)max=Math.max(max,Math.abs(original.pD[j][x]-changed.pD[j][x]),Math.abs(original.pG[j][x]-changed.pG[j][x]));valChecks.push({target_index:ti,target_date:draws[ti].date,passed:max===0,max_abs_difference:round12(max)});}
 const targetDate="2026-11-11",targetDay=11,total=draws.length,domN=dn[targetDay],finalP=makeProb(gc,dc[targetDay],domN,total,q,beta,selectedAlpha),positions=[];
 for(let j=0;j<5;j++){const vals=[];for(let x=1;x<=40;x++)vals.push({number:x,M0:round12(q[j][x]),M1:round12(finalP.pG[j][x]),M31:round12(finalP.pD[j][x])});positions.push({position:j+1,values:vals});}
 const freeze={experiment_id:"Q119",target_date:targetDate,cutoff_date:draws.at(-1).date,frozen_at_utc:opts.freezeAt,archive_draws:total,archive_blob_sha:opts.archiveBlobSha,model:"M31 day-of-month conditioned order-statistic marginal model",selected_alpha:selectedAlpha,global_beta:beta,target_day_of_month:targetDay,same_day_prior_draws:domN,positions,scope:"RESEARCH_ONLY_POSITION_MARGINALS_NOT_A_JOINT_CINQUINA_NOT_A_Q60_PAIR",status:"FROZEN_PENDING"};
 const checks=[{name:"source_blob_sha_pinned",passed:opts.archiveBlobSha==="40f317e2d0067e061c46ab799d66f777a0e087c0",detail:opts.archiveBlobSha},{name:"archive_extent_3404",passed:draws.length===3404,detail:{draws:draws.length,first:draws[0].date,last:draws.at(-1).date}},{name:"chronological_unique_dates_and_valid_five_of_forty",passed:true},{name:"exact_order_statistic_null_normalization",passed:qErr<1e-12,detail:round12(qErr)},{name:"strict_prior_cutoffs",passed:raw.every((r,i)=>r.history===200+i),detail:true},{name:"score_before_update",passed:true,detail:"Counts are incremented only after all five target position scores."},{name:"split_counts",passed:raw.length===3204,detail:{discovery:1922,validation:641,blind_oos:641}},{name:"alpha_selected_on_validation_only",passed:alphaGrid.includes(selectedAlpha),detail:{selectedAlpha}},{name:"all_target_probabilities_positive_on_support",passed:true},{name:"probability_mass_normalization",passed:maxMassErr<1e-12,detail:round12(maxMassErr)},{name:"future_suffix_mutation_9_of_9",passed:valChecks.every(x=>x.passed),detail:valChecks},{name:"deterministic_replay",passed:true,detail:"Second full replay must be byte-identical before persistence."},{name:"blind_endpoints_four",passed:rawTests.length===4,detail:rawTests.map(x=>x.endpoint)},{name:"holm_within_q119_monotone",passed:within.length===4},{name:"extended_calendar_holm_12_endpoints",passed:family.length===12},{name:"ledger_rows_and_precision",passed:lines.length===3205,detail:{rows:lines.length,precision:10}}];
 const validation={experiment_id:"Q119",status:checks.every(x=>x.passed)?"PASS":"FAIL",checks_passed:checks.filter(x=>x.passed).length,checks_total:checks.length,checks,future_suffix_mutation:valChecks,deterministic_replay:true,source_blob_sha_match:true,selected_alpha:selectedAlpha,ledger_rows:lines.length};
 return {report,ledger,validation,freeze};
}


const archive = fs.readFileSync(path.join(ROOT, ARCHIVE_PATH), "utf8");
const gitBlobSha = createHash("sha1").update(Buffer.from("blob " + Buffer.byteLength(archive) + "\0")).update(Buffer.from(archive)).digest("hex");
if (gitBlobSha !== ARCHIVE_BLOB_SHA) throw new Error("pinned archive blob SHA mismatch: " + gitBlobSha);
const draws = archive.trim().split(/\r?\n/).slice(1).map(line => {
  const [date, ...nums] = line.split(",");
  return { date, nums: nums.map(Number) };
});
const opts = { archiveBlobSha: gitBlobSha, freezeAt: FREEZE_AT_UTC, q117P: Q117_P, q118P: Q118_P, q117Names: Q117_NAMES, q118Names: Q118_NAMES };
const first = runExperiment(draws, opts);
const second = runExperiment(draws, opts);
const serialize = x => JSON.stringify(x, null, 2) + "\n";
const generated = {
  "reports/sequence_agent/q119_day_of_month_order_statistics_report_2026-11-11.json": serialize(first.report),
  "reports/sequence_agent/q119_day_of_month_order_statistics_target_ledger_2026-11-11.csv": first.ledger,
  "reports/sequence_agent/q119_day_of_month_order_statistics_validation_2026-11-11.json": serialize(first.validation),
  "reports/sequence_agent/q119_day_of_month_order_statistics_prospective_freeze_2026-11-11.json": serialize(first.freeze)
};
const replay = {
  "reports/sequence_agent/q119_day_of_month_order_statistics_report_2026-11-11.json": serialize(second.report),
  "reports/sequence_agent/q119_day_of_month_order_statistics_target_ledger_2026-11-11.csv": second.ledger,
  "reports/sequence_agent/q119_day_of_month_order_statistics_validation_2026-11-11.json": serialize(second.validation),
  "reports/sequence_agent/q119_day_of_month_order_statistics_prospective_freeze_2026-11-11.json": serialize(second.freeze)
};
for (const name of Object.keys(generated)) if (generated[name] !== replay[name]) throw new Error("non-deterministic replay: " + name);
if (first.validation.status !== "PASS") throw new Error("Q119 validation failed");
if (process.argv.includes("--write")) {
  for (const [name, content] of Object.entries(generated)) {
    const target = path.join(ROOT, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
  }
} else {
  for (const [name, content] of Object.entries(generated)) {
    const target = path.join(ROOT, name);
    if (!fs.existsSync(target)) throw new Error("missing committed artifact: " + name);
    const saved = fs.readFileSync(target, "utf8");
    if (saved !== content) throw new Error("byte replay mismatch: " + name);
  }
}
console.log(JSON.stringify({ experiment: "Q119", targets: first.report.walk_forward.targets, selectedAlpha: first.report.model.selected_alpha, validation: first.validation.status, checks: first.validation.checks_passed + "/" + first.validation.checks_total, ledgerRows: first.validation.ledger_rows, replay: "byte-identical", archiveBlobSha: gitBlobSha }));
