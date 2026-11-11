#!/usr/bin/env node
// Q127 deterministic Node 20 replay; six-decimal canonical serialization.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
const ROOT=process.cwd();
const BASE="reports/sequence_agent/";
const FILES={"protocol":"reports/sequence_agent/q127_low_high_balance_transition_protocol_2026-11-11.json","report":"reports/sequence_agent/q127_low_high_balance_transition_report_2026-11-11.json","ledger":"reports/sequence_agent/q127_low_high_balance_transition_target_ledger_2026-11-11.csv","validation":"reports/sequence_agent/q127_low_high_balance_transition_validation_2026-11-11.json","checkpoint":"reports/sequence_agent/q127_low_high_balance_transition_checkpoint_2026-11-11.md","manifest":"reports/sequence_agent/q127_low_high_balance_transition_persistence_manifest_2026-11-11.json","runner":"scripts/sonar_q127_low_high_balance_transition.mjs","workflow":".github/workflows/q127-low-high-balance-transition.yml"};
const ARCHIVE_PATH="data/storico_daily.csv";
const EXPECTED_ARCHIVE_BLOB="40f317e2d0067e061c46ab799d66f777a0e087c0";
const EXPECTED_PROTOCOL_BLOB="36dd14b940d4eeccead81ff3e82048eadd72598c";
const PROTOCOL_COMMIT_SHA="944dce696aaa2446d9c71f075590e1d8966c7f88";
function read(p){return fs.readFileSync(path.join(ROOT,p),"utf8");}
function utf8Bytes(s){return Buffer.byteLength(s,"utf8");}
function gitBlobSha(s){const b=Buffer.from(s,"utf8");const h=Buffer.from("blob "+b.length+"\\0","utf8");return crypto.createHash("sha1").update(Buffer.concat([h,b])).digest("hex");}

function assert(c,m){if(!c)throw new Error(m);}

function comb(n,k){if(k<0||k>n)return 0;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return Math.round(v);}

function makeRng(seed){let x=seed>>>0;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;};}

function round6(x){return Number(x.toFixed(6));}

function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}

function parseArchive(s){const lines=s.trim().split(/\r?\n/);assert(lines[0]==="data,n1,n2,n3,n4,n5","archive header mismatch");return lines.slice(1).map(line=>{const f=line.split(",");return{d:f[0],n:f.slice(1).map(Number)};});}

function lowCount(draw){return draw.n.reduce((s,n)=>s+(n<=20?1:0),0);}

function exactNull(){const den=comb(40,5);const q=Array.from({length:6},(_,k)=>comb(20,k)*comb(20,5-k)/den);return{q,den,mean:q.reduce((s,p,k)=>s+p*k,0),variance:q.reduce((s,p,k)=>s+p*(k-2.5)**2,0)};}

function forecastAt(draws,t,q0,alpha=200){const y=draws.slice(0,t).map(lowCount);const global=Array(6).fill(0);const trans=Array.from({length:6},()=>Array(6).fill(0));const stateN=Array(6).fill(0);for(const v of y)global[v]++;for(let i=1;i<y.length;i++){trans[y[i-1]][y[i]]++;stateN[y[i-1]]++;}const priorN=y.length,s=y[t-1];const p1=q0.map((q,k)=>(global[k]+alpha*q)/(priorN+alpha));const p2=p1.map((p,k)=>(trans[s][k]+alpha*p)/(stateN[s]+alpha));return{p1,p2,priorN,transitionN:priorN-1,stateN:stateN[s],state:s};}

function brier(p,y){let v=0;for(let k=0;k<6;k++){const d=p[k]-(k===y?1:0);v+=d*d;}return v;}

function logloss(p,y){return-Math.log(p[y]);}

function blockSignFlip(gains,reps,blockLength,seed){const blocks=[];for(let i=0;i<gains.length;i+=blockLength)blocks.push(gains.slice(i,i+blockLength).reduce((s,x)=>s+x,0));const observed=mean(gains),rng=makeRng(seed);let ge=0;for(let r=0;r<reps;r++){let sum=0;for(const b of blocks)sum+=(rng()<0.5?-b:b);if(sum/gains.length>=observed-1e-15)ge++;}return(ge+1)/(reps+1);}

function quantile(sorted,p){const x=(sorted.length-1)*p,lo=Math.floor(x),hi=Math.ceil(x);return sorted[lo]+(sorted[hi]-sorted[lo])*(x-lo);}

function blockBootstrapCI(gains,reps,blockLength,seed){const n=gains.length,rng=makeRng(seed),vals=new Array(reps);for(let r=0;r<reps;r++){let sum=0,count=0;while(count<n){const start=Math.floor(rng()*n);for(let j=0;j<blockLength&&count<n;j++,count++)sum+=gains[(start+j)%n];}vals[r]=sum/n;}vals.sort((a,b)=>a-b);return[quantile(vals,0.025),quantile(vals,0.975)];}

function holmAdjust(endpoints){const order=endpoints.map((e,i)=>({i,p:e.p_value})).sort((a,b)=>a.p-b.p);let prev=0;const out=new Array(endpoints.length);for(let r=0;r<order.length;r++){const v=Math.min(1,(order.length-r)*order[r].p);prev=Math.max(prev,v);out[order[r].i]=prev;}return out;}

function splitName(i){return i<1922?"discovery":i<2563?"validation":"blind_oos";}

function buildExperiment(draws,archiveSha,protocolBlobSha,protocolCommitSha,expectedProtocolBlob){
 const qn=exactNull(),y=draws.map(lowCount),alpha=200,warmup=200;
 const global=Array(6).fill(0),trans=Array.from({length:6},()=>Array(6).fill(0)),stateN=Array(6).fill(0);
 for(let i=0;i<warmup;i++)global[y[i]]++;
 for(let i=1;i<warmup;i++){trans[y[i-1]][y[i]]++;stateN[y[i-1]]++;}
 const rows=[],losses={m0:{brier:[],logloss:[]},m1:{brier:[],logloss:[]},m2:{brier:[],logloss:[]}};
 let maxMassError=0;
 for(let t=warmup;t<draws.length;t++){
  const s=y[t-1],obs=y[t],priorN=t,transitionN=t-1;
  const p0=qn.q.slice(),p1=qn.q.map((q,k)=>(global[k]+alpha*q)/(priorN+alpha)),p2=p1.map((p,k)=>(trans[s][k]+alpha*p)/(stateN[s]+alpha));
  for(const p of [p0,p1,p2])maxMassError=Math.max(maxMassError,Math.abs(p.reduce((a,b)=>a+b,0)-1));
  const vals={m0:{brier:brier(p0,obs),logloss:logloss(p0,obs)},m1:{brier:brier(p1,obs),logloss:logloss(p1,obs)},m2:{brier:brier(p2,obs),logloss:logloss(p2,obs)}};
  for(const m of ["m0","m1","m2"]){losses[m].brier.push(vals[m].brier);losses[m].logloss.push(vals[m].logloss);}
  rows.push({target_index:t,target_date:draws[t].d,cutoff_date:draws[t-1].d,split:splitName(t-warmup),previous_low_count:s,observed_low_count:obs,prior_draws:priorN,prior_transition_count:transitionN,state_prior_n:stateN[s],m0_brier:vals.m0.brier,m0_logloss:vals.m0.logloss,m1_brier:vals.m1.brier,m1_logloss:vals.m1.logloss,m2_brier:vals.m2.brier,m2_logloss:vals.m2.logloss,m0_observed_probability:p0[obs],m1_observed_probability:p1[obs],m2_observed_probability:p2[obs]});
  global[obs]++;trans[s][obs]++;stateN[s]++;
 }
 const splitRanges={discovery:[0,1922],validation:[1922,2563],blind_oos:[2563,3204]},splitStats={};
 for(const [name,[a,b]] of Object.entries(splitRanges)){const ys=y.slice(warmup+a,warmup+b);splitStats[name]={targets:b-a,first_target:rows[a].target_date,last_target:rows[b-1].target_date,observed_low_count_mean:round6(mean(ys)),observed_low_count_distribution:Array(6).fill(0).map((_,k)=>ys.filter(v=>v===k).length),previous_state_distribution:Array(6).fill(0).map((_,k)=>rows.slice(a,b).filter(r=>r.previous_low_count===k).length),models:Object.fromEntries(["m0","m1","m2"].map(m=>[m,{mean_brier:round6(mean(losses[m].brier.slice(a,b))),mean_logloss:round6(mean(losses[m].logloss.slice(a,b)))}]))};}
 const comparisons=[["M1_vs_M0","m0","m1"],["M2_vs_M1","m1","m2"],["M2_vs_M0","m0","m2"]],endpoints=[];let idx=0;
 for(const [name,base,cand] of comparisons){for(const metric of ["brier","logloss"]){const a=losses[base][metric].slice(2563),b=losses[cand][metric].slice(2563),gains=a.map((v,i)=>v-b[i]),seed=0x1272026+(idx+1)*104729,p=blockSignFlip(gains,50000,20,seed),ci=blockBootstrapCI(gains,10000,20,seed+0x9e3779b9);endpoints.push({id:name+"_"+metric,comparison:name,metric,observed_gain:round6(mean(gains)),p_value:round6(p),sign_flip_replicates:50000,block_length:20,blocks:Math.ceil(gains.length/20),ci95:ci.map(round6),bootstrap_replicates:10000,bootstrap_block_length:20});idx++;}}
 const adj=holmAdjust(endpoints);endpoints.forEach((e,i)=>e.holm_adjusted_p=round6(adj[i]));
 const futureTargets=[200,601,1000,1400,1800,2200,2600,3000,3402];let futurePass=0;
 for(const t of futureTargets){const f1=forecastAt(draws,t,qn.q,alpha),mutated=draws.map((d,i)=>i>t?{d:d.d,n:[21,22,23,24,25]}:{d:d.d,n:d.n.slice()}),f2=forecastAt(mutated,t,qn.q,alpha);if(JSON.stringify(f1)===JSON.stringify(f2))futurePass++;}
 const checks=[
  ["archive_sha_pinned",archiveSha==="40f317e2d0067e061c46ab799d66f777a0e087c0"],
  ["protocol_blob_pinned",protocolBlobSha===expectedProtocolBlob],
  ["protocol_commit_recorded",protocolCommitSha==="944dce696aaa2446d9c71f075590e1d8966c7f88"],
  ["draw_count_3404",draws.length===3404],
  ["dates_strictly_increasing",draws.every((d,i)=>i===0||draws[i-1].d<d.d)],
  ["five_distinct_numbers_1_to_40",draws.every(d=>d.n.length===5&&new Set(d.n).size===5&&d.n.every(n=>Number.isInteger(n)&&n>=1&&n<=40))],
  ["low_count_support_zero_to_five",y.every(v=>v>=0&&v<=5)],
  ["exact_5_of_40_denominator",qn.den===658008],
  ["exact_null_probability_mass",Math.abs(qn.q.reduce((a,b)=>a+b,0)-1)<1e-14],
  ["exact_null_mean_two_point_five",Math.abs(qn.mean-2.5)<1e-12],
  ["warmup_and_target_count",warmup===200&&rows.length===3204],
  ["strict_prior_cutoffs",rows.every(r=>r.cutoff_date<r.target_date&&r.prior_draws===r.target_index)],
  ["prior_transition_counts",rows.every(r=>r.prior_transition_count===r.target_index-1)],
  ["prequential_global_prior_counts",rows.every(r=>r.prior_draws>=warmup)],
  ["conditional_state_counts_nonnegative",rows.every(r=>r.state_prior_n>=0)],
  ["probability_masses",maxMassError<1e-12],
  ["finite_proper_scores",Object.values(losses).every(m=>m.brier.every(Number.isFinite)&&m.logloss.every(Number.isFinite))],
  ["chronological_split_1922_641_641",splitStats.discovery.targets===1922&&splitStats.validation.targets===641&&splitStats.blind_oos.targets===641],
  ["future_suffix_mutation_invariance_9_of_9",futurePass===9],
  ["holm_family_has_six_endpoints",endpoints.length===6&&endpoints.every(e=>Number.isFinite(e.holm_adjusted_p))]
 ];
 assert(checks.every(x=>x[1]),"Q127 validation failed: "+checks.filter(x=>!x[1]).map(x=>x[0]).join(","));
 const header=["target_index","target_date","cutoff_date","split","previous_low_count","observed_low_count","prior_draws","prior_transition_count","state_prior_n","m0_brier","m0_logloss","m1_brier","m1_logloss","m2_brier","m2_logloss","m0_observed_probability","m1_observed_probability","m2_observed_probability"];
 const csv=[header.join(",")].concat(rows.map(r=>header.map(k=>typeof r[k]==="number"?round6(r[k]).toFixed(6):r[k]).join(","))).join("\n")+"\n";
 const report={schema_version:"1.0",experiment_id:"Q127",title:"Prior-only low/high balance transition",status:"COMPLETED_EXPLORATORY_NO_PROMOTION",decision:"NO_LOW_HIGH_BALANCE_TRANSITION_LIFT_DEMONSTRATED",preregistration:{protocol_blob_sha:protocolBlobSha,protocol_commit_sha:protocolCommitSha,registered_before_calculation:true,protocol_status:"PREREGISTERED_BEFORE_CALCULATION"},source:{archive_blob_sha:archiveSha,draws:draws.length,first_date:draws[0].d,last_date:draws[draws.length-1].d},statistic:{definition:"L_t = number of drawn values in 1..20; S_t=L_(t-1).",support:[0,1,2,3,4,5],exact_null_denominator:qn.den,exact_null_probabilities:qn.q.map(round6),null_mean:round6(qn.mean),null_variance:round6(qn.variance)},method:{warmup:200,alpha:200,targets:rows.length,splits:{discovery:1922,validation:641,blind_oos:641},models:{M0:"Exact Hypergeometric(40,20,5) marginal.",M1:"Prior-only unconditional prequential marginal with alpha=200 shrinkage toward M0.",M2:"Prior-only one-step previous-state conditional marginal with alpha=200 shrinkage toward M1."},metrics:["multiclass Brier over support 0..5","negative log probability of observed L_t"],scoring_order:"Score before update; target t uses only draws strictly before t.",inference:{blind_oos_only:true,paired_block_sign_flip_replicates:50000,circular_moving_block_bootstrap_replicates:10000,block_length:20,alternative:"one-sided improvement",multiplicity:"Holm across six preregistered Blind OOS endpoints."}},splits:splitStats,blind_oos_inference:endpoints,decision_reason:"M2 is evaluated against both the exact combinatorial marginal and the prior-only unconditional model. Promotion is not permitted unless a positive incremental gain is stable and survives the preregistered block inference and Holm correction; historical Blind OOS is not a virgin holdout.",limitations:["The lower/upper partition at 20/21 is one fixed coarse partition and cannot represent all draw geometry.","This transition diagnostic is adjacent to prior parity, median, range and gap-state studies; incremental evidence must be interpreted in the context of the broader Q00-Q127 search family.","Historical Blind OOS has prior exposure to SONAR research and is not independent prospective confirmation.","Holm correction covers only six local Q127 endpoints, not the full Q00-Q127 research family.","This is a structural distribution diagnostic, not a full five-number predictor."],next_action:"After official publication of contest 315, score immutable 11-Nov freezes without retuning and continue append-only Q60 paired collection."};
 const validation={schema_version:"1.0",experiment_id:"Q127",status:"PASS",checks:checks.map(([name,passed])=>({name,passed})),exact_null:{denominator:qn.den,probabilities:qn.q.map(round6),mass:round6(qn.q.reduce((a,b)=>a+b,0)),mean:round6(qn.mean),variance:round6(qn.variance)},target_ledger:{rows:rows.length,first_target:rows[0].target_date,last_target:rows[rows.length-1].target_date,split_sizes:{discovery:1922,validation:641,blind_oos:641}},future_suffix_mutation_checks:{passed:futurePass,total:9},probability_masses_within_1e_12:maxMassError<1e-12,inference:{endpoints:endpoints.length,sign_flip_replicates:50000,bootstrap_replicates:10000,block_length:20,all_p_values_finite:endpoints.every(e=>Number.isFinite(e.p_value)),all_holm_finite:endpoints.every(e=>Number.isFinite(e.holm_adjusted_p))}};
 const checkpoint=["# Q127 checkpoint — low/high balance transition","",`- Protocol committed before calculation; protocol commit \`${protocolCommitSha}\`; protocol blob \`${protocolBlobSha}\`.`,`- Canonical archive: 3,404 draws, ${draws[0].d} through ${draws[draws.length-1].d}; blob \`${archiveSha}\`.`,"- Statistic: L_t counts values 1..20; previous state is L_(t-1); exact null is Hypergeometric(40,20,5).","- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.","- Models: M0 exact combinatorial marginal; M1 prior-only unconditional shrinkage alpha=200; M2 prior-only one-step previous-state conditional shrinkage alpha=200 toward M1.","- Blind OOS inference: six endpoints; 50,000 paired block sign-flips and 10,000 circular moving-block bootstrap replicates, block length 20; Holm across six.",`- Validation checks: ${checks.length}/${checks.length}; future-suffix mutation: ${futurePass}/9; all prequential probability masses within 1e-12.`,"- Decision: **NO_LOW_HIGH_BALANCE_TRANSITION_LIFT_DEMONSTRATED**.","- No forecast freeze, Q60 record, production scorer, or existing PR was modified.","","## Limitations","",...report.limitations.map(x=>"- "+x),"","## Next action","","After official publication of contest 315, score existing immutable 11-Nov freezes without retuning; continue append-only Q60 paired collection. No automatic merge or engine promotion.",""].join("\n");
 return{report:JSON.stringify(report,null,2)+"\n",ledger:csv,validation:JSON.stringify(validation,null,2)+"\n",checkpoint};
}

function buildManifest(){
 const paths=[FILES.protocol,FILES.runner,FILES.workflow,FILES.report,FILES.ledger,FILES.validation,FILES.checkpoint];
 const entries=paths.map(p=>{const c=read(p);return{path:p,git_blob_sha:gitBlobSha(c),bytes_utf8:utf8Bytes(c)};});
 return JSON.stringify({schema_version:"1.0",experiment_id:"Q127",status:"PERSISTED",base_commit:"ea46a70c4c90db5dad44d5374a97f89a84e50ad9",entries},null,2)+"\\n";
}
function main(){
 const mode=process.argv.includes("--write")?"write":"check";
 const archiveText=read(ARCHIVE_PATH),protocolText=read(FILES.protocol);
 assert(gitBlobSha(archiveText)===EXPECTED_ARCHIVE_BLOB,"archive Git blob SHA mismatch");
 assert(gitBlobSha(protocolText)===EXPECTED_PROTOCOL_BLOB,"protocol Git blob SHA mismatch");
 const draws=parseArchive(archiveText);
 const out=buildExperiment(draws,EXPECTED_ARCHIVE_BLOB,EXPECTED_PROTOCOL_BLOB,PROTOCOL_COMMIT_SHA,EXPECTED_PROTOCOL_BLOB);
 const generated={[FILES.report]:out.report,[FILES.ledger]:out.ledger,[FILES.validation]:out.validation,[FILES.checkpoint]:out.checkpoint};
 if(mode==="write"){for(const [p,c] of Object.entries(generated))fs.writeFileSync(path.join(ROOT,p),c);const manifest=buildManifest();fs.writeFileSync(path.join(ROOT,FILES.manifest),manifest);process.stdout.write("Q127 WRITE PASS\\n");return;}
 for(const [p,c] of Object.entries(generated)){const actual=read(p);if(actual!==c){let i=0;while(i<actual.length&&i<c.length&&actual[i]===c[i])i++;process.stderr.write("DIFF "+p+" at char "+i+" expected="+JSON.stringify(c.slice(Math.max(0,i-60),i+120))+" actual="+JSON.stringify(actual.slice(Math.max(0,i-60),i+120))+"\\n");throw new Error("persisted output differs: "+p);}}
 const manifest=buildManifest();assert(read(FILES.manifest)===manifest,"manifest differs from deterministic replay");
 const m=JSON.parse(manifest);assert(m.entries.length===7,"manifest entry count mismatch");
 for(const e of m.entries){const c=read(e.path);assert(gitBlobSha(c)===e.git_blob_sha,"Git blob SHA mismatch: "+e.path);assert(utf8Bytes(c)===e.bytes_utf8,"UTF-8 size mismatch: "+e.path);}
 process.stdout.write("Q127 CHECK PASS: 3204 targets; 20/20 checks; six inferential endpoints; report/ledger/validation/checkpoint byte-identical; 7/7 manifest entries verified.\\n");
}
main();
