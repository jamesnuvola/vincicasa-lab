import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const EXPECTED_ARCHIVE_BLOB_SHA = "5d2efd70684e918b27d8f06386d545647898336d";
const OUTPUT_JSON = "reports/position_specific_range_residual/PSR12_results_20261108.json";
const OUTPUT_DISCOVERY = "reports/position_specific_range_residual/PSR12_target_ledger_discovery_20261108.csv";
const OUTPUT_VALIDATION = "reports/position_specific_range_residual/PSR12_target_ledger_validation_20261108.csv";
const OUTPUT_BLIND = "reports/position_specific_range_residual/PSR12_target_ledger_blind_oos_20261108.csv";


export function lag1ScoreVector(q0,condCount,exposure,state,alpha){
  if(q0.length!==40||condCount.length!==40||exposure.length!==40)throw new Error("score vector must have 40 numbers");
  if(!Number.isFinite(alpha)||alpha<0)throw new Error("alpha must be nonnegative");
  return q0.map((p,j)=>state.includes(j+1)?(condCount[j]+alpha*p)/(exposure[j]+alpha):p);
}
export function runExperiment(csv,opts={}){
  const lines=csv.trim().split(String.fromCharCode(10)).map(x=>x.endsWith(String.fromCharCode(13))?x.slice(0,-1):x);
  if(lines[0]!=="data,n1,n2,n3,n4,n5")throw new Error("bad header");
  const dates=[],draws=[];
  for(let i=1;i<lines.length;i++){const row=lines[i].split(",");if(row.length!==6)throw new Error("bad row "+i);dates.push(row[0]);const nums=row.slice(1).map(Number);if(nums.some(n=>!Number.isInteger(n)||n<1||n>40)||new Set(nums).size!==5)throw new Error("invalid draw "+i);nums.sort((a,b)=>a-b);draws.push(nums);}
  for(let i=1;i<dates.length;i++)if(dates[i]<=dates[i-1])throw new Error("dates not strictly ascending");
  const N=draws.length,warm=opts.warmup??200,split1=opts.split1??1800,split2=opts.split2??2600,alphaGrid=opts.alphaGrid??[0,25,50,100,200,500,1000],block=7,B=opts.inferenceReplicates??20000,BB=opts.bootstrapReplicates??2000;
  if(!opts.synthetic&&(N!==3401||dates[N-1]!=="2026-11-07"))throw new Error("archive pin mismatch");
  if(opts.expectedBlobSha&&opts.expectedBlobSha!=="5d2efd70684e918b27d8f06386d545647898336d")throw new Error("expected archive Git blob mismatch");
  if(!(warm>1&&warm<split1&&split1<split2&&split2<N))throw new Error("invalid split boundaries");
  if(Math.floor((N-split2)/block)<2)throw new Error("blind tail too short for block inference");
  if(new Set(alphaGrid).size!==alphaGrid.length||alphaGrid.some(a=>!Number.isFinite(a)||a<0))throw new Error("invalid alpha grid");
  const globalCount=Array(40).fill(0),condCount=Array(40).fill(0),exposure=Array(40).fill(0);
  for(let u=0;u<warm;u++)for(const n of draws[u])globalCount[n-1]++;
  for(let u=1;u<warm;u++){const state=draws[u-1],outcome=draws[u];for(const n of state)exposure[n-1]++;for(const n of state)if(outcome.includes(n))condCount[n-1]++;}
  const records=[];
  for(let t=warm;t<N;t++){
    const q0=globalCount.map(c=>c/t),state=draws[t-1],actual=draws[t],baseTop=rank(q0),baseHit=hits(baseTop.slice(0,5),actual),baseBrier=brier(q0,actual),baseLL=logloss(q0,actual),byAlpha={};
    const globalTotal=globalCount.reduce((s,x)=>s+x,0),exposureTotal=exposure.reduce((s,x)=>s+x,0);
    if(globalTotal!==5*t)throw new Error("global prior count total mismatch at "+t);
    if(exposureTotal!==5*(t-1))throw new Error("lag exposure total mismatch at "+t);
    for(const alpha of alphaGrid){const scores=lag1ScoreVector(q0,condCount,exposure,state,alpha);if(scores.some(p=>!Number.isFinite(p)||p<0||p>1))throw new Error("invalid probability at target "+t+" alpha "+alpha);const top=rank(scores);byAlpha[alpha]={hit:hits(top.slice(0,5),actual),brier:brier(scores,actual),ll:logloss(scores,actual),top5:top.slice(0,5),scores};}
    const cutoff=dates[t-1],date=dates[t],trainN=t,strictPrefixOk=(trainN===t&&cutoff<date);if(!strictPrefixOk)throw new Error("cutoff leakage at "+t);
    records.push({t,date,cutoff,trainN,state:state.slice(),actual:actual.slice(),globalTotal,exposureTotal,strictPrefixOk,baseTop5:baseTop.slice(0,5),baseHit,baseBrier,baseLL,byAlpha});
    for(const n of actual)globalCount[n-1]++;
    for(const n of state)exposure[n-1]++;
    for(const n of state)if(actual.includes(n))condCount[n-1]++;
  }
  function rank(scores){return Array.from({length:40},(_,j)=>j+1).sort((a,b)=>scores[b-1]-scores[a-1]||a-b);}
  function hits(top,actual){let h=0;for(const n of top)if(actual.includes(n))h++;return h;}
  function brier(p,actual){let s=0;for(let j=0;j<40;j++){const y=actual.includes(j+1)?1:0,d=p[j]-y;s+=d*d;}return s/40;}
  function logloss(p,actual){let s=0;for(let j=0;j<40;j++){const y=actual.includes(j+1)?1:0,q=Math.max(1e-12,Math.min(1-1e-12,p[j]));s-=y*Math.log(q)+(1-y)*Math.log(1-q);}return s/40;}
  const splits={discovery:records.filter(r=>r.t<split1),validation:records.filter(r=>r.t>=split1&&r.t<split2),blind_oos:records.filter(r=>r.t>=split2)};
  const metrics={};
  for(const [split,rows] of Object.entries(splits)){metrics[split]={n:rows.length,first:rows[0].date,last:rows[rows.length-1].date,by_alpha:{}};for(const alpha of alphaGrid){const hm=rows.reduce((s,r)=>s+r.byAlpha[alpha].hit,0),hb=rows.reduce((s,r)=>s+r.baseHit,0),bg=rows.reduce((s,r)=>s+r.baseBrier-r.byAlpha[alpha].brier,0)/rows.length,llg=rows.reduce((s,r)=>s+r.baseLL-r.byAlpha[alpha].ll,0)/rows.length;metrics[split].by_alpha[alpha]={model_top5_hit_count:hm,baseline_top5_hit_count:hb,model_hit_share:hm/(5*rows.length),baseline_hit_share:hb/(5*rows.length),delta_hit_share:(hm-hb)/(5*rows.length),brier_gain:bg,logloss_gain:llg};}}
  const v=metrics.validation.by_alpha,selected=alphaGrid.slice().sort((a,b)=>v[b].brier_gain-v[a].brier_gain||v[b].logloss_gain-v[a].logloss_gain||v[b].delta_hit_share-v[a].delta_hit_share||b-a)[0];
  const blind=splits.blind_oos,fullN=Math.floor(blind.length/block),used=fullN*block,endpoints=["hit","brier","ll"];
  function diffAt(r,alpha,e){if(e==="hit")return r.byAlpha[alpha].hit-r.baseHit;if(e==="brier")return r.baseBrier-r.byAlpha[alpha].brier;return r.baseLL-r.byAlpha[alpha].ll;}
  let seed=opts.seed??20261108;function rand(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;}
  const infer={n_total:blind.length,n_used_blocks:fullN,n_used_targets:used,n_omitted_tail:blind.length-used,block_length:block,replicates_signflip:B,replicates_bootstrap:BB,by_alpha:{}},rawTests=[];
  for(const alpha of alphaGrid){infer.by_alpha[alpha]={};for(const e of endpoints){const d=blind.slice(0,used).map(r=>diffAt(r,alpha,e)),sums=[];for(let b=0;b<fullN;b++){let s=0;for(let k=0;k<block;k++)s+=d[b*block+k];sums.push(s);}const obs=sums.reduce((s,x)=>s+x,0);let ge=0;for(let rep=0;rep<B;rep++){let stat=0;for(const x of sums)stat+=(rand()<0.5?-1:1)*x;if(stat>=obs-1e-14)ge++;}const p=(ge+1)/(B+1),boot=[];for(let rep=0;rep<BB;rep++){let total=0;for(let k=0;k<fullN;k++){const start=Math.floor(rand()*blind.length);for(let j=0;j<block;j++)total+=diffAt(blind[(start+j)%blind.length],alpha,e);}boot.push(total/used);}boot.sort((a,b)=>a-b);const lo=boot[Math.floor(.025*BB)],hi=boot[Math.floor(.975*BB)],mean=obs/used;infer.by_alpha[alpha][e]={mean_gain:mean,ci95:[lo,hi],p_raw:p};rawTests.push({alpha,endpoint:e,p});}}
  function choose(n,k){if(k<0||k>n)return 0;k=Math.min(k,n-k);let x=1;for(let i=1;i<=k;i++)x=x*(n-k+i)/i;return x;}
  const den=choose(40,5),mass=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/den);let dist=[1];for(let t=0;t<blind.length;t++){const next=Array(dist.length+5).fill(0);for(let i=0;i<dist.length;i++)for(let k=0;k<=5;k++)next[i+k]+=dist[i]*mass[k];dist=next;}
  const uniform={per_target_expected_hits:0.625,expected_total_hits:blind.length*0.625,expected_hit_share:0.125,exact_tail_p_by_alpha:{}};
  for(const alpha of alphaGrid){const observed=metrics.blind_oos.by_alpha[alpha].model_top5_hit_count;let tail=0;for(let k=observed;k<dist.length;k++)tail+=dist[k];const p=Math.min(1,tail);uniform.exact_tail_p_by_alpha[alpha]={observed_total_hits:observed,p_raw:p};rawTests.push({alpha,endpoint:"uniform_top5",p});}
  rawTests.sort((a,b)=>a.p-b.p);let prev=0;rawTests.forEach((x,i)=>{const adj=Math.min(1,Math.max(prev,(rawTests.length-i)*x.p));x.p_holm=adj;prev=adj;});
  for(const x of rawTests){if(x.endpoint==="uniform_top5")uniform.exact_tail_p_by_alpha[x.alpha].p_holm=x.p_holm;else infer.by_alpha[x.alpha][x.endpoint].p_holm=x.p_holm;}
  const ledgerHeader=["target_date","history_cutoff","train_draws","lag1_state","selected_alpha_validation","baseline_top5","baseline_hits","model_top5","model_hits","actual_numbers","brier_gain","logloss_gain","global_count_total","lag_exposure_total","strict_prefix_ok"],ledgerRows=[];
  for(const r of records){const m=r.byAlpha[selected];ledgerRows.push([r.date,r.cutoff,r.trainN,r.state.join(" "),selected,r.baseTop5.join(" "),r.baseHit,m.top5.join(" "),m.hit,r.actual.join(" "),(r.baseBrier-m.brier).toFixed(12),(r.baseLL-m.ll).toFixed(12),r.globalTotal,r.exposureTotal,r.strictPrefixOk?1:0].join(","));}
  const nl=String.fromCharCode(10),header=ledgerHeader.join(",");
  const ledgers={discovery:header+nl+ledgerRows.filter((_,i)=>records[i].t<split1).join(nl)+nl,validation:header+nl+ledgerRows.filter((_,i)=>records[i].t>=split1&&records[i].t<split2).join(nl)+nl,blind_oos:header+nl+ledgerRows.filter((_,i)=>records[i].t>=split2).join(nl)+nl};
  const summary={experiment_id:"SONAR_PSR12_LAG1_INCLUSION_TRANSITION",status:"EXPLORATORY_NO_PROMOTION",archive:{draws:N,first_date:dates[0],last_date:dates[N-1],expected_blob_sha:"5d2efd70684e918b27d8f06386d545647898336d"},walkforward:{warmup:warm,targets:records.length,split_boundaries:{discovery:[warm,split1],validation:[split1,split2],blind_oos:[split2,N]},metrics,selected_alpha_validation:selected,selection_rule:"maximize validation Brier gain; tie-break log-loss gain, Top-5 hit-share gain, then larger alpha"},inference:infer,uniform_null:uniform,controls:{strict_prefix_checks:records.filter(r=>r.strictPrefixOk&&r.trainN===r.t&&r.cutoff<r.date).length,total:records.length,global_prior_count_total_checks:records.length,lag_exposure_total_checks:records.length,probability_range_checks:records.length,ledger_rows:records.length,n_unique_target_keys:new Set(records.map(r=>r.t+"|"+r.date)).size,n_omitted_tail_for_inference:blind.length-used}};
  return {summary,ledgers};
}


function main() {
  const csv = readFileSync(resolve("data/storico_daily.csv"), "utf8");
  const gitBlobSha = createHash("sha1").update(Buffer.from("blob " + Buffer.byteLength(csv) + String.fromCharCode(0))).update(csv).digest("hex");
  if (gitBlobSha !== EXPECTED_ARCHIVE_BLOB_SHA) throw new Error("canonical archive Git blob mismatch: " + gitBlobSha);
  const result = runExperiment(csv, { expectedBlobSha: gitBlobSha });
  const nl = String.fromCharCode(10);
  const outputs = new Map([
    [OUTPUT_JSON, JSON.stringify(result.summary, null, 2) + nl],
    [OUTPUT_DISCOVERY, result.ledgers.discovery],
    [OUTPUT_VALIDATION, result.ledgers.validation],
    [OUTPUT_BLIND, result.ledgers.blind_oos]
  ]);
  if (process.argv.includes("--verify")) {
    for (const [path, expected] of outputs) {
      const actual = readFileSync(resolve(path), "utf8");
      if (actual !== expected) throw new Error("PSR12 exact replay mismatch: " + path);
    }
    process.stdout.write("PSR12_REPLAY_OK blob=" + gitBlobSha + " targets=" + result.summary.walkforward.targets + " ledgers=3" + nl);
  } else {
    for (const [path, content] of outputs) writeFileSync(resolve(path), content, "utf8");
    process.stdout.write("PSR12_OUTPUTS_WRITTEN blob=" + gitBlobSha + " targets=" + result.summary.walkforward.targets + " ledgers=3" + nl);
  }
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) main();
