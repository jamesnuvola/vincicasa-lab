#!/usr/bin/env node
// Q128 deterministic Node 20 replay. Research-only; no production or freeze writes.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
const ROOT=process.cwd();
const P={
 archive:"data/storico_daily.csv",
 protocol:"reports/sequence_agent/q128_adjacency_run_transition_protocol_2026-11-11.json",
 report:"reports/sequence_agent/q128_adjacency_run_transition_report_2026-11-11.json",
 ledger:"reports/sequence_agent/q128_adjacency_run_transition_target_ledger_2026-11-11.csv",
 validation:"reports/sequence_agent/q128_adjacency_run_transition_validation_2026-11-11.json",
 checkpoint:"reports/sequence_agent/q128_adjacency_run_transition_checkpoint_2026-11-11.md",
 manifest:"reports/sequence_agent/q128_adjacency_run_transition_persistence_manifest_2026-11-11.json",
 runner:"scripts/sonar_q128_adjacency_run_transition.mjs",
 workflow:".github/workflows/q128-adjacency-run-transition.yml"
};
const EXPECTED_ARCHIVE_BLOB="40f317e2d0067e061c46ab799d66f777a0e087c0";
const EXPECTED_PROTOCOL_BLOB="25c6a837251719412b41d0f9a5161adfedeacbdc";
const EXPECTED_PROTOCOL_COMMIT="637528eeea81f4cd34ed62aad8ba2d324f74ce67";
const EXPECTED_MAIN_COMMIT="ea46a70c4c90db5dad44d5374a97f89a84e50ad9";
function read(p){return fs.readFileSync(path.join(ROOT,p),"utf8");}
function utf8Bytes(s){return Buffer.byteLength(s,"utf8");}
function gitBlobSha(s){const b=Buffer.from(s,"utf8");const h=Buffer.from("blob "+b.length+"\0","utf8");return crypto.createHash("sha1").update(Buffer.concat([h,b])).digest("hex");}
function assert(c,m){if(!c)throw new Error(m);}
function comb(n,k){if(k<0||k>n)return 0;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return Math.round(v);}
function round6(x){return Number(x.toFixed(6));}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
function adjCount(nums){const a=nums.slice().sort((x,y)=>x-y);let n=0;for(let i=1;i<a.length;i++)if(a[i]-a[i-1]===1)n++;return n;}
function parseArchive(s){const lines=s.trim().split(/\r?\n/);assert(lines[0]==="data,n1,n2,n3,n4,n5","archive header mismatch");return lines.slice(1).map(line=>{const f=line.split(",");return{date:f[0],n:f.slice(1).map(Number)};});}
function exactNull(){const den=comb(40,5),counts=Array.from({length:5},(_,a)=>comb(4,a)*comb(36,5-a));const q=counts.map(x=>x/den);return{den,counts,q,mean:q.reduce((s,p,a)=>s+p*a,0)};}
function brier(p,y){let v=0;for(let k=0;k<5;k++){const d=p[k]-(k===y?1:0);v+=d*d;}return v;}
function logloss(p,y){return-Math.log(p[y]);}
function makeRng(seed){let x=seed>>>0;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;};}
function blockSignFlip(gains,reps,blockLength,seed){const blocks=[];for(let i=0;i<gains.length;i+=blockLength)blocks.push(gains.slice(i,i+blockLength).reduce((s,x)=>s+x,0));const observed=mean(gains),rng=makeRng(seed);let ge=0;for(let r=0;r<reps;r++){let sum=0;for(const b of blocks)sum+=(rng()<0.5?-b:b);if(sum/gains.length>=observed-1e-15)ge++;}return(ge+1)/(reps+1);}
function quantile(sorted,p){const x=(sorted.length-1)*p,lo=Math.floor(x),hi=Math.ceil(x);return sorted[lo]+(sorted[hi]-sorted[lo])*(x-lo);}
function blockBootstrapCI(gains,reps,blockLength,seed){const n=gains.length,rng=makeRng(seed),vals=new Array(reps);for(let r=0;r<reps;r++){let sum=0,count=0;while(count<n){const start=Math.floor(rng()*n);for(let j=0;j<blockLength&&count<n;j++,count++)sum+=gains[(start+j)%n];}vals[r]=sum/n;}vals.sort((a,b)=>a-b);return[quantile(vals,0.025),quantile(vals,0.975)];}
function holmAdjust(endpoints){const order=endpoints.map((e,i)=>({i,p:e.p_value})).sort((a,b)=>a.p-b.p);let prev=0;const out=new Array(endpoints.length);for(let r=0;r<order.length;r++){const v=Math.min(1,(order.length-r)*order[r].p);prev=Math.max(prev,v);out[order[r].i]=prev;}return out;}
function splitName(i){return i<1922?"discovery":i<2563?"validation":"blind_oos";}
function forecastFromDraws(draws,t,q0,alpha){const y=draws.slice(0,t).map(d=>adjCount(d.n));const global=Array(5).fill(0),trans=Array.from({length:5},()=>Array(5).fill(0)),stateN=Array(5).fill(0);for(const v of y)global[v]++;for(let j=1;j<y.length;j++){trans[y[j-1]][y[j]]++;stateN[y[j-1]]++;}const state=y[y.length-1],p1=q0.map((q,k)=>(global[k]+alpha*q)/(t+alpha)),p2=p1.map((p,k)=>(trans[state][k]+alpha*p)/(stateN[state]+alpha));return{p1,p2,state,stateN:stateN[state],priorDraws:t,priorTransitions:t-1};}
function run(){
 const archiveText=read(P.archive),protocolText=read(P.protocol),protocol=JSON.parse(protocolText);
 assert(gitBlobSha(archiveText)===EXPECTED_ARCHIVE_BLOB,"canonical archive Git blob mismatch");
 assert(gitBlobSha(protocolText)===EXPECTED_PROTOCOL_BLOB,"preregistered protocol Git blob mismatch");
 assert(protocol.base_main_commit===EXPECTED_MAIN_COMMIT,"protocol base main mismatch");
 assert(protocol.source.blob_sha===EXPECTED_ARCHIVE_BLOB,"protocol archive pin mismatch");
 assert(EXPECTED_PROTOCOL_COMMIT==="637528eeea81f4cd34ed62aad8ba2d324f74ce67","protocol commit constant mismatch");
 const draws=parseArchive(archiveText),A=draws.map(d=>adjCount(d.n)),q0=exactNull(),alpha=200,warm=200;
 const global=Array(5).fill(0),trans=Array.from({length:5},()=>Array(5).fill(0)),stateN=Array(5).fill(0);
 for(let i=0;i<warm;i++)global[A[i]]++;
 for(let j=1;j<warm;j++){trans[A[j-1]][A[j]]++;stateN[A[j-1]]++;}
 const rows=[],loss={m0:{brier:[],logloss:[]},m1:{brier:[],logloss:[]},m2:{brier:[],logloss:[]}};
 let maxMassError=0;
 for(let t=warm;t<draws.length;t++){
  const state=A[t-1],observed=A[t],priorN=global.reduce((s,x)=>s+x,0),priorTransitions=stateN.reduce((s,x)=>s+x,0);
  const p0=q0.q.slice(),p1=q0.q.map((q,k)=>(global[k]+alpha*q)/(priorN+alpha)),p2=p1.map((p,k)=>(trans[state][k]+alpha*p)/(stateN[state]+alpha));
  for(const p of [p0,p1,p2])maxMassError=Math.max(maxMassError,Math.abs(p.reduce((s,x)=>s+x,0)-1));
  const v={m0:{brier:brier(p0,observed),logloss:logloss(p0,observed)},m1:{brier:brier(p1,observed),logloss:logloss(p1,observed)},m2:{brier:brier(p2,observed),logloss:logloss(p2,observed)}};
  for(const m of ["m0","m1","m2"]){loss[m].brier.push(v[m].brier);loss[m].logloss.push(v[m].logloss);}
  rows.push({target_index:t,target_date:draws[t].date,cutoff_date:draws[t-1].date,split:splitName(t-warm),previous_adjacency_count:state,observed_adjacency_count:observed,prior_draws:priorN,prior_transition_count:priorTransitions,prior_state_count:stateN[state],m0_brier:v.m0.brier,m0_logloss:v.m0.logloss,m1_brier:v.m1.brier,m1_logloss:v.m1.logloss,m2_brier:v.m2.brier,m2_logloss:v.m2.logloss,m0_observed_probability:p0[observed],m1_observed_probability:p1[observed],m2_observed_probability:p2[observed]});
  global[observed]++;trans[state][observed]++;stateN[state]++;
 }
 const ranges={discovery:[0,1922],validation:[1922,2563],blind_oos:[2563,3204]},splits={};
 for(const [name,[a,b]] of Object.entries(ranges)){
  const rr=rows.slice(a,b),obs=rr.map(r=>r.observed_adjacency_count),states=rr.map(r=>r.previous_adjacency_count),obsCounts=Array(5).fill(0),stateCounts=Array(5).fill(0);
  for(const x of obs)obsCounts[x]++;for(const x of states)stateCounts[x]++;
  splits[name]={targets:b-a,first_target:rr[0].target_date,last_target:rr[rr.length-1].target_date,observed_adjacency_mean:round6(mean(obs)),observed_count_distribution:obsCounts,previous_state_distribution:stateCounts,models:{}};
  for(const m of ["m0","m1","m2"])splits[name].models[m]={mean_brier:round6(mean(loss[m].brier.slice(a,b))),mean_logloss:round6(mean(loss[m].logloss.slice(a,b)))};
 }
 const comparisons=[["M1_vs_M0","m0","m1"],["M2_vs_M1","m1","m2"],["M2_vs_M0","m0","m2"]],endpoints=[];let endpointIndex=0;
 for(const [comparison,base,candidate] of comparisons)for(const metric of ["brier","logloss"]){
  const gains=loss[base][metric].slice(2563).map((v,i)=>v-loss[candidate][metric][2563+i]),seed=0x1282026+(endpointIndex+1)*104729;
  endpoints.push({id:comparison+"_"+metric,comparison,metric,observed_gain:round6(mean(gains)),p_value:round6(blockSignFlip(gains,50000,20,seed)),ci95:blockBootstrapCI(gains,10000,20,seed+0x9e3779b9).map(round6),sign_flip_replicates:50000,bootstrap_replicates:10000,block_length:20,block_count:Math.ceil(gains.length/20)});
  endpointIndex++;
 }
 const adjusted=holmAdjust(endpoints);endpoints.forEach((e,i)=>e.holm_adjusted_p=round6(adjusted[i]));
 const futureTargets=[200,601,1000,1400,1800,2200,2600,3000,3402];let futurePass=0;
 for(const t of futureTargets){const original=forecastFromDraws(draws,t,q0.q,alpha),mutated=draws.map((d,i)=>i>=t?{date:d.date,n:[1,2,3,4,5]}:d),after=forecastFromDraws(mutated,t,q0.q,alpha);if(JSON.stringify(original)===JSON.stringify(after))futurePass++;}
 const checks=[
  ["archive_blob_pinned",gitBlobSha(archiveText)===EXPECTED_ARCHIVE_BLOB],
  ["protocol_blob_pinned",gitBlobSha(protocolText)===EXPECTED_PROTOCOL_BLOB],
  ["protocol_commit_pinned",EXPECTED_PROTOCOL_COMMIT==="637528eeea81f4cd34ed62aad8ba2d324f74ce67"],
  ["main_base_pinned",protocol.base_main_commit===EXPECTED_MAIN_COMMIT],
  ["archive_row_count_3404",draws.length===3404],
  ["archive_date_range",draws[0].date==="2017-07-17"&&draws[draws.length-1].date==="2026-11-10"],
  ["dates_strictly_increasing",draws.every((d,i)=>i===0||draws[i-1].date<d.date)],
  ["five_distinct_numbers_in_range",draws.every(d=>d.n.length===5&&new Set(d.n).size===5&&d.n.every(n=>Number.isInteger(n)&&n>=1&&n<=40))],
  ["draws_sorted",draws.every(d=>d.n.every((n,i)=>i===0||d.n[i-1]<n))],
  ["adjacency_support_zero_to_four",A.every(a=>a>=0&&a<=4)],
  ["exact_subset_denominator_658008",q0.den===658008],
  ["exact_count_sum_658008",q0.counts.reduce((s,x)=>s+x,0)===658008],
  ["exact_null_mass_one",Math.abs(q0.q.reduce((s,x)=>s+x,0)-1)<1e-14],
  ["exact_null_mean_half",Math.abs(q0.mean-0.5)<1e-12],
  ["warmup_200_target_count_3204",warm===200&&rows.length===3204],
  ["strict_prior_target_cutoffs",rows.every(r=>r.cutoff_date<r.target_date&&r.prior_draws===r.target_index)],
  ["transition_counts_strictly_prior",rows.every(r=>r.prior_transition_count===r.target_index-1)],
  ["state_counts_are_prior_only",rows.every(r=>r.prior_state_count>=0&&r.prior_state_count<=r.prior_transition_count)],
  ["score_before_update_and_target_excluded",rows.every(r=>r.prior_draws===r.target_index&&r.prior_transition_count===r.target_index-1)],
  ["all_probability_masses_normalized",maxMassError<1e-12],
  ["finite_proper_scores",Object.values(loss).every(m=>m.brier.every(Number.isFinite)&&m.logloss.every(Number.isFinite))],
  ["chronological_splits_1922_641_641",splits.discovery.targets===1922&&splits.validation.targets===641&&splits.blind_oos.targets===641],
  ["future_target_suffix_mutation_9_of_9",futurePass===9],
  ["six_finite_inferential_endpoints",endpoints.length===6&&endpoints.every(e=>Number.isFinite(e.p_value)&&Number.isFinite(e.holm_adjusted_p))]
 ];
 assert(checks.every(x=>x[1]),"Q128 validation failed: "+checks.filter(x=>!x[1]).map(x=>x[0]).join(","));
 const cols=["target_index","target_date","cutoff_date","split","previous_adjacency_count","observed_adjacency_count","prior_draws","prior_transition_count","prior_state_count","m0_brier","m0_logloss","m1_brier","m1_logloss","m2_brier","m2_logloss","m0_observed_probability","m1_observed_probability","m2_observed_probability"];
 const ledger=[cols.join(",")].concat(rows.map(r=>cols.map(k=>typeof r[k]==="number"?round6(r[k]).toFixed(6):r[k]).join(","))).join("\n")+"\n";
 const report={
  experiment:"Q128",title:"Prior-only adjacent-run-count transition diagnostic",status:"COMPLETED_RESEARCH_ONLY",
  source:{path:P.archive,git_blob_sha:EXPECTED_ARCHIVE_BLOB,draws:draws.length,first_date:draws[0].date,last_date:draws[draws.length-1].date},
  preregistration:{protocol_path:P.protocol,protocol_blob_sha:EXPECTED_PROTOCOL_BLOB,protocol_commit:EXPECTED_PROTOCOL_COMMIT,base_main_commit:EXPECTED_MAIN_COMMIT,committed_before_calculation:true},
  statistic:{name:"A_t",definition:"Count of adjacent integer pairs among the five sorted values; equivalently 5 minus the number of consecutive runs.",support:[0,1,2,3,4]},
  exact_null:{formula:"q0(a)=C(4,a)*C(36,5-a)/C(40,5)",denominator:q0.den,counts:q0.counts,probabilities:q0.q.map(round6),expected_mean:round6(q0.mean)},
  design:{warmup_draws:warm,targets:rows.length,alpha:alpha,score_before_update:true,strict_prior_only:true,split_sizes:{discovery:1922,validation:641,blind_oos:641},tuning:"none",models:{M0:"exact combinatorial marginal",M1:"unconditional prequential shrinkage alpha=200 toward M0",M2:"one-step previous-adjacency-state conditional shrinkage alpha=200 toward current M1"}},
  splits:splits,
  inference:{blind_oos_targets:641,comparisons:3,endpoints:endpoints,holm_family_size:6,sign_flip_replicates:50000,bootstrap_replicates:10000,block_length:20,alternative:"positive loss gain favors candidate",note:"Holm applies only to the six preregistered Q128 endpoints."},
  decision:"NO_ADJACENT_RUN_TRANSITION_LIFT_DEMONSTRATED",
  interpretation:"M1 and M2 have worse mean Brier and log-loss than the exact combinatorial baseline in all three chronological splits. M2 is also worse than M1 in both Blind OOS proper scores; all six Blind OOS gains are negative and all Holm-adjusted p-values equal 1.000.",
  integrity:{checks_passed:checks.length,checks_total:checks.length,future_suffix_mutation_passed:futurePass,future_suffix_mutation_total:futureTargets.length,max_probability_mass_error:maxMassError},
  limitations:["Historical Blind OOS is not a virgin holdout.","Holm correction is local to six Q128 endpoints, not the full Q00-Q128 research family.","The adjacent-run statistic compresses each draw to one scalar and is not a five-number or quintet probability model.","Q98 previously tested a broader lag-1 full-draw geometry kernel; Q128 is a narrow exact-statistic audit and is not independent of that broader family.","No prospective confirmation is available while contest 315 remains officially pending."],
  governance:{research_only:true,production_scorer_changed:false,forecast_freezes_changed:false,q60_changed:false,engine_promoted:false,automatic_merge:false,protected_prs:[6,7,8]}
 };
 const validation={experiment:"Q128",status:"PASS",checks:checks.map(([id,passed])=>({id,passed})),checks_passed:checks.length,checks_total:checks.length,future_suffix_mutation:{passed:futurePass,total:futureTargets.length,target_indices:futureTargets},max_probability_mass_error:maxMassError,strict_prior_targets:rows.length,ledger_rows:rows.length,inference_endpoints:endpoints.length,holm_family_size:6};
 const reportText=JSON.stringify(report,null,2)+"\n",validationText=JSON.stringify(validation,null,2)+"\n";
 const checkpointText=[
  "# Q128 checkpoint — adjacent-run-count transition",
  "",
  "- Protocol committed before calculation: "+EXPECTED_PROTOCOL_COMMIT+"; protocol blob "+EXPECTED_PROTOCOL_BLOB+".",
  "- Base main: "+EXPECTED_MAIN_COMMIT+"; canonical archive blob "+EXPECTED_ARCHIVE_BLOB+", 3,404 draws through 2026-11-10.",
  "- Statistic: number of adjacent integer pairs in the sorted five-number draw, support 0..4.",
  "- Exact null: C(4,a) * C(36,5-a) / C(40,5); denominator 658,008; expected count 0.5.",
  "- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.",
  "- Models: M0 exact null; M1 unconditional prequential alpha=200; M2 previous-state conditional alpha=200 toward M1.",
  "- Blind OOS: all six proper-score gains negative; all six Holm-adjusted p-values 1.000; decision NO_ADJACENT_RUN_TRANSITION_LIFT_DEMONSTRATED.",
  "- Validation: "+checks.length+"/"+checks.length+" checks; future-suffix mutation "+futurePass+"/"+futureTargets.length+"; max probability-mass error "+maxMassError+".",
  "- No forecast freeze, Q60 record, production scorer, or protected PR was changed.",
  "",
  "## Limitations",
  "",
  "- Historical Blind OOS is not a virgin holdout; Q98's broad lag-1 geometry kernel is related prior research.",
  "- Holm correction is local to Q128's six endpoints, not the complete Q00-Q128 research family.",
  "- This is a structural distribution diagnostic, not a quintet predictor.",
  "",
  "## Next action",
  "",
  "After official publication of contest 315, append the verified outcome and score only immutable existing freezes; continue append-only Q60 paired collection.",
  "",
  "## Replay recovery",
  "",
  "- The first persisted-head Node 20 replay failed before execution because `utf8Bytes` was declared twice in the ES module. The duplicate trailing declaration was removed; the statistical algorithm and results are unchanged.",
  "",
  "## CI status at artifact generation",
  "",
  "The exact-head Node 20 replay and general repository CI must be observed after this branch is pushed. Do not infer CI success from the local calculation."
 ].join("\n")+"\n";
 const artifacts=[[P.protocol,protocolText],[P.report,reportText],[P.ledger,ledger],[P.validation,validationText],[P.checkpoint,checkpointText],[P.runner,read(P.runner)],[P.workflow,read(P.workflow)]];
 const manifest={experiment:"Q128",base_main_commit:EXPECTED_MAIN_COMMIT,protocol_commit:EXPECTED_PROTOCOL_COMMIT,archive_blob_sha:EXPECTED_ARCHIVE_BLOB,entries:artifacts.map(([p,s])=>({path:p,git_blob_sha1:gitBlobSha(s),utf8_bytes:utf8Bytes(s)}))};
 const manifestText=JSON.stringify(manifest,null,2)+"\n";
 return{reportText,ledger,validationText,checkpointText,manifestText,report,validation,checks,rows};
}
const out=run();
for(const [p,expected] of [[P.report,out.reportText],[P.ledger,out.ledger],[P.validation,out.validationText],[P.checkpoint,out.checkpointText],[P.manifest,out.manifestText]])assert(read(p)===expected,"persisted artifact mismatch: "+p);
console.log("Q128 CHECK PASS: "+out.rows.length+" targets; "+out.checks.length+"/"+out.checks.length+" checks; six inferential endpoints; report/ledger/validation/checkpoint byte-identical; 7/7 manifest entries verified.");
