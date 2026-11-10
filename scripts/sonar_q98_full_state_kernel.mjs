"use strict";
const fs = require("node:fs");
const crypto = require("node:crypto");
const PROTOCOL_PATH = "reports/sequence_agent/q98_full_state_kernel_protocol_2026-11-10.json";
const REPORT_PATH = "reports/sequence_agent/q98_full_state_kernel_report_2026-11-10.json";
const LEDGER_PATH = "reports/sequence_agent/q98_full_state_kernel_target_ledger_2026-11-10.csv";

const H = [0.5, 0.75, 1.0, 1.5];
const ALPHA = 200;
const BLOCK_LENGTH = 20;
function assert(cond, msg) { if (!cond) throw new Error(msg); }
function roundN(x, digits=9) {
  const z = Math.abs(x) < 0.5 * Math.pow(10, -digits) ? 0 : x;
  return Number(z.toFixed(digits));
}
function fmt(x) { return roundN(x, 9).toFixed(9); }
function mean(a) { return a.reduce((s,x)=>s+x,0)/a.length; }
function comb(n,k) {
  if (k < 0 || n < 0 || k > n) return 0;
  k = Math.min(k, n-k);
  let v=1;
  for (let i=1;i<=k;i++) v = v*(n-k+i)/i;
  return v;
}
function buildPriors() {
  const den = comb(40,5);
  const priors=[];
  for (let j=0;j<5;j++) {
    const p=[];
    for (let n=j+1;n<=j+36;n++) p.push(comb(n-1,j)*comb(40-n,4-j)/den);
    const mass=p.reduce((a,b)=>a+b,0);
    assert(Math.abs(mass-1)<1e-12, "exact order-statistic prior does not sum to one at position "+(j+1));
    let mu=0;
    for(let i=0;i<36;i++) mu+=(j+1+i)*p[i];
    let variance=0;
    for(let i=0;i<36;i++) variance+=Math.pow((j+1+i)-mu,2)*p[i];
    priors.push({p,mean:mu,sd:Math.sqrt(variance),mass});
  }
  return priors;
}
function parseCsv(csv) {
  const lines=csv.trimEnd().split(/\r?\n/);
  assert(lines.length>1 && lines[0]==="data,n1,n2,n3,n4,n5","unexpected archive CSV header");
  const draws=[];
  for(let i=1;i<lines.length;i++) {
    const a=lines[i].split(",");
    assert(a.length===6,"invalid archive row "+(i+1));
    const date=a[0], nums=a.slice(1).map(Number);
    assert(/^\d{4}-\d{2}-\d{2}$/.test(date),"invalid date at row "+(i+1));
    assert(nums.length===5 && nums.every(Number.isInteger),"invalid numeric draw at row "+(i+1));
    assert(nums[0]>=1 && nums[4]<=40 && nums.every((v,k)=>k===0 || nums[k-1]<v),"invalid sorted 5-of-40 draw at row "+(i+1));
    if(draws.length) assert(draws[draws.length-1].date<date,"archive dates not strictly increasing");
    draws.push({date,nums});
  }
  return draws;
}
function standardize(draws, priors) {
  return draws.map(d=>d.nums.map((x,j)=>(x-priors[j].mean)/priors[j].sd));
}
function top5Indices(p, j) {
  return Array.from({length:36},(_,i)=>i).sort((a,b)=>(p[b]-p[a]) || (a-b)).slice(0,5);
}
function brier(p, actualIndex) {
  let s=0;
  for(let i=0;i<36;i++) { const d=p[i]-(i===actualIndex?1:0); s+=d*d; }
  return s;
}
function predictTarget(t, draws, z, priors, bandwidths=H, alpha=ALPHA, p5OnlyH=1.5) {
  assert(t>=2 && t<draws.length,"target index outside prediction range");
  const counts=bandwidths.map(()=>Array.from({length:5},()=>Array(36).fill(0)));
  const weightSums=bandwidths.map(()=>0);
  const p5Counts=Array(36).fill(0);
  let p5WeightSum=0;
  const current=z[t-1];
  for(let u=1;u<t;u++) {
    const histState=z[u-1];
    let d2=0;
    for(let j=0;j<5;j++) { const d=current[j]-histState[j]; d2+=d*d; }
    d2/=5;
    for(let k=0;k<bandwidths.length;k++) {
      const h=bandwidths[k];
      const w=Math.exp(-d2/(2*h*h));
      weightSums[k]+=w;
      for(let j=0;j<5;j++) {
        const idx=draws[u].nums[j]-(j+1);
        counts[k][j][idx]+=w;
      }
    }
    const d5=current[4]-histState[4];
    const w5=Math.exp(-(d5*d5)/(2*p5OnlyH*p5OnlyH));
    p5WeightSum+=w5;
    p5Counts[draws[u].nums[4]-5]+=w5;
  }
  const probsByH=[];
  let maxNormError=0;
  for(let k=0;k<bandwidths.length;k++) {
    const perPos=[];
    for(let j=0;j<5;j++) {
      const p=Array.from({length:36},(_,i)=>(alpha*priors[j].p[i]+counts[k][j][i])/(alpha+weightSums[k]));
      const err=Math.abs(p.reduce((a,b)=>a+b,0)-1);
      maxNormError=Math.max(maxNormError,err);
      assert(p.every(v=>Number.isFinite(v)&&v>=0&&v<=1),"invalid model probability");
      perPos.push(p);
    }
    probsByH.push(perPos);
  }
  const p5Only=Array.from({length:36},(_,i)=>(alpha*priors[4].p[i]+p5Counts[i])/(alpha+p5WeightSum));
  const p5Err=Math.abs(p5Only.reduce((a,b)=>a+b,0)-1);
  maxNormError=Math.max(maxNormError,p5Err);
  assert(Math.abs(maxNormError)<1e-10,"probability normalization error");
  return {probsByH,p5Only,maxTrainingOutcomeIndex:t-1,trainingPairs:t-1,maxNormError,weightSums,p5WeightSum};
}
function scoreTarget(t, draws, pred, priors, bandwidths=H) {
  const actual=draws[t].nums;
  const baselineTop5=priors.map((q,j)=>top5Indices(q.p,j));
  const nullPosBrier=[], nullPosHits=[];
  let nullTop5=0;
  for(let j=0;j<5;j++) {
    const idx=actual[j]-(j+1);
    nullPosBrier.push(brier(priors[j].p,idx));
    const hit=baselineTop5[j].includes(idx)?1:0;
    nullPosHits.push(hit); nullTop5+=hit;
  }
  const modelBrier=[], modelP5Brier=[], modelTop5=[], modelPosBrier=[], modelPosHits=[];
  for(let k=0;k<bandwidths.length;k++) {
    let bsum=0, hsum=0;
    const pb=[], ph=[];
    for(let j=0;j<5;j++) {
      const idx=actual[j]-(j+1), p=pred.probsByH[k][j];
      pb.push(brier(p,idx));
      const hit=top5Indices(p,j).includes(idx)?1:0;
      ph.push(hit); hsum+=hit; bsum+=pb[j];
    }
    modelBrier.push(bsum/5);
    modelP5Brier.push(pb[4]);
    modelTop5.push(hsum);
    modelPosBrier.push(pb);
    modelPosHits.push(ph);
  }
  const p5Index=actual[4]-5;
  const p5OnlyBrier=brier(pred.p5Only,p5Index);
  const p5OnlyTop5=top5Indices(pred.p5Only,4).includes(p5Index)?1:0;
  return {brierNull:mean(nullPosBrier),brierModel:modelBrier,top5NullHits:nullTop5,top5ModelHits:modelTop5,p5BrierNull:nullPosBrier[4],p5BrierFull:modelP5Brier,p5BrierOnly:p5OnlyBrier,p5Top5NullHits:nullPosHits[4],p5Top5Full:modelPosHits.map(x=>x[4]),p5Top5Only:p5OnlyTop5,posBrierNull:nullPosBrier,posBrierModel:modelPosBrier,posTop5Null:nullPosHits,posTop5Model:modelPosHits};
}
function mulberry32(seed) {
  return function() {
    let t=seed+=0x6D2B79F5;
    t=Math.imul(t^(t>>>15),t|1);
    t^=t+Math.imul(t^(t>>>7),t|61);
    return ((t^(t>>>14))>>>0)/4294967296;
  };
}
function syntheticDraws(n,seed) {
  const rng=mulberry32(seed), out=[];
  for(let i=0;i<n;i++) {
    const a=Array.from({length:40},(_,k)=>k+1);
    for(let j=39;j>0;j--) { const k=Math.floor(rng()*(j+1)); [a[j],a[k]]=[a[k],a[j]]; }
    out.push({date:"2000-01-01",nums:a.slice(0,5).sort((x,y)=>x-y)});
  }
  return out;
}
function runSelfTests() {
  const priors=buildPriors();
  const draws=syntheticDraws(304,98103);
  const z=standardize(draws,priors);
  const a=predictTarget(300,draws,z,priors,H,ALPHA,1.5);
  const b=predictTarget(300,draws,z,priors,H,ALPHA,1.5);
  assert(JSON.stringify(a)===JSON.stringify(b),"prediction replay is not deterministic");
  assert(a.trainingPairs===299 && a.maxTrainingOutcomeIndex===299 && a.maxTrainingOutcomeIndex<300,"strict-prior training boundary failed");
  const mutated=draws.map(d=>({date:d.date,nums:d.nums.slice()}));
  mutated[300]={date:mutated[300].date,nums:[1,9,17,28,40]};
  mutated[301]={date:mutated[301].date,nums:[2,8,16,31,39]};
  const zMut=standardize(mutated,priors);
  const c=predictTarget(300,mutated,zMut,priors,H,ALPHA,1.5);
  assert(JSON.stringify(a)===JSON.stringify(c),"target/future mutation changed pre-target prediction");
  assert(a.maxNormError<1e-10,"synthetic probability normalization failed");
  return {passed:5,tests:["exact priors normalize","strict-prior boundary","target/future mutation invariance","probability normalization","deterministic prediction replay"]};
}
function percentile(sorted,p) {
  const x=(sorted.length-1)*p, lo=Math.floor(x), hi=Math.ceil(x);
  if(lo===hi) return sorted[lo];
  return sorted[lo]+(sorted[hi]-sorted[lo])*(x-lo);
}
function holm(tests) {
  const order=tests.map((t,i)=>({i,p:t.p_raw})).sort((a,b)=>a.p-b.p || a.i-b.i);
  let running=0;
  for(let r=0;r<order.length;r++) {
    const adj=Math.min(1,(order.length-r)*order[r].p);
    running=Math.max(running,adj);
    tests[order[r].i].p_holm=running;
  }
  return tests;
}
function inferFamily(tests, blockLength, bootRep, signRep, seedBoot, seedSign) {
  const n=tests[0].values.length, m=tests.length;
  const boot=Array.from({length:m},()=>new Array(bootRep));
  const rngB=mulberry32(seedBoot);
  for(let r=0;r<bootRep;r++) {
    const sums=Array(m).fill(0);
    let count=0;
    while(count<n) {
      const start=Math.floor(rngB()*n);
      for(let q=0;q<blockLength && count<n;q++,count++) {
        const idx=(start+q)%n;
        for(let k=0;k<m;k++) sums[k]+=tests[k].values[idx];
      }
    }
    for(let k=0;k<m;k++) boot[k][r]=sums[k]/n;
  }
  const blocks=Math.ceil(n/blockLength);
  const blockSums=tests.map(t=>{
    const a=[];
    for(let start=0;start<n;start+=blockLength) a.push(t.values.slice(start,Math.min(n,start+blockLength)).reduce((s,x)=>s+x,0));
    return a;
  });
  const observed=tests.map(t=>mean(t.values));
  const exceed=Array(m).fill(0);
  const rngS=mulberry32(seedSign);
  for(let r=0;r<signRep;r++) {
    const sums=Array(m).fill(0);
    for(let b=0;b<blocks;b++) {
      const sign=rngS()<0.5?-1:1;
      for(let k=0;k<m;k++) sums[k]+=sign*blockSums[k][b];
    }
    for(let k=0;k<m;k++) if(sums[k]/n>=observed[k]-1e-15) exceed[k]++;
  }
  for(let k=0;k<m;k++) {
    const sorted=boot[k].slice().sort((a,b)=>a-b);
    tests[k].mean=roundN(observed[k]);
    tests[k].ci95=[roundN(percentile(sorted,0.025)),roundN(percentile(sorted,0.975))];
    tests[k].p_raw=(exceed[k]+1)/(signRep+1);
    tests[k].block_count=blocks;
    delete tests[k].values;
  }
  return holm(tests);
}
function splitName(i, counts) {
  if(i<counts.discovery) return "discovery";
  if(i<counts.discovery+counts.validation) return "validation";
  return "blind_oos_historical";
}
function summarizeSplit(rows, hGrid) {
  const out={targets:rows.length,first_target:rows[0].date,last_target:rows[rows.length-1].date,exact_prior:{mean_multiclass_brier:roundN(mean(rows.map(r=>r.brierNull))),mean_top5_hits_per_target:roundN(mean(rows.map(r=>r.top5NullHits))),mean_p5_brier:roundN(mean(rows.map(r=>r.p5BrierNull))),mean_p5_top5_hits_per_target:roundN(mean(rows.map(r=>r.p5Top5NullHits)))},full_state_kernel:{}};
  for(let k=0;k<hGrid.length;k++) {
    const b=mean(rows.map(r=>r.brierModel[k]));
    const th=mean(rows.map(r=>r.top5ModelHits[k]));
    const p5=mean(rows.map(r=>r.p5BrierFull[k]));
    const p5h=mean(rows.map(r=>r.p5Top5Full[k]));
    const perPos=[];
    for(let j=0;j<5;j++) {
      perPos.push({position:"P"+(j+1),brier_gain_vs_exact_prior:roundN(mean(rows.map(r=>r.posBrierNull[j]-r.posBrierModel[k][j]))),top5_hit_gain_per_target:roundN(mean(rows.map(r=>r.posTop5Model[k][j]-r.posTop5Null[j])))});
    }
    out.full_state_kernel[String(hGrid[k])]={mean_multiclass_brier:roundN(b),mean_brier_gain_vs_exact_prior:roundN(out.exact_prior.mean_multiclass_brier-b),mean_top5_hits_per_target:roundN(th),mean_top5_hit_gain_vs_exact_prior:roundN(th-out.exact_prior.mean_top5_hits_per_target),mean_p5_brier:roundN(p5),mean_p5_brier_gain_vs_exact_prior:roundN(out.exact_prior.mean_p5_brier-p5),mean_p5_top5_hits_per_target:roundN(p5h),per_position:perPos};
  }
  out.fixed_p5_only_comparator={h:1.5,mean_p5_brier:roundN(mean(rows.map(r=>r.p5BrierOnly))),mean_p5_brier_gain_vs_exact_prior:roundN(out.exact_prior.mean_p5_brier-mean(rows.map(r=>r.p5BrierOnly))),mean_p5_top5_hits_per_target:roundN(mean(rows.map(r=>r.p5Top5Only))),mean_p5_top5_hit_gain_vs_exact_prior:roundN(mean(rows.map(r=>r.p5Top5Only))-out.exact_prior.mean_p5_top5_hits_per_target)};
  return out;
}
function runExperiment(csv, protocol) {
  const selfTests=runSelfTests();
  const draws=parseCsv(csv);
  assert(draws.length===protocol.source.draws,"archive draw count differs from preregistration");
  assert(draws[0].date===protocol.source.first_date && draws[draws.length-1].date===protocol.source.last_date,"archive date range differs from preregistration");
  const priors=buildPriors(), z=standardize(draws,priors);
  const counts=protocol.walk_forward.chronological_splits;
  const start=protocol.walk_forward.zero_based_target_index_start;
  const targetCount=counts.discovery+counts.validation+counts.blind_oos_historical;
  assert(draws.length-start===targetCount,"split sizes do not reconcile to target count");
  const hGrid=protocol.model.bandwidth_grid, alpha=protocol.model.fixed_prior_strength_alpha, p5OnlyH=protocol.model.p5_only_comparator.match(/h=([0-9.]+)/)?.[1] ? Number(protocol.model.p5_only_comparator.match(/h=([0-9.]+)/)[1]) : 1.5;
  const rows=[], ledgerLines=[];
  const header=["target_date","history_cutoff","split","target_index_zero_based","training_pairs","previous_draw","brier_null","brier_h_0_5","brier_h_0_75","brier_h_1_0","brier_h_1_5","top5_null_hits","top5_h_0_5","top5_h_0_75","top5_h_1_0","top5_h_1_5","p5_brier_null","p5_brier_full_h_1_5","p5_brier_only_h_1_5","p5_top5_null_hits","p5_top5_full_h_1_5","p5_top5_only_h_1_5"];
  ledgerLines.push(header.join(","));
  let strictChecks=0, normalizationChecks=0, maxNormError=0;
  for(let t=start;t<draws.length;t++) {
    const pred=predictTarget(t,draws,z,priors,hGrid,alpha,p5OnlyH);
    assert(pred.maxTrainingOutcomeIndex<t,"target leakage: training outcome reaches target");
    assert(pred.trainingPairs===t-1,"unexpected historical pair count");
    strictChecks++;
    normalizationChecks+=hGrid.length*5+1;
    maxNormError=Math.max(maxNormError,pred.maxNormError);
    const score=scoreTarget(t,draws,pred,priors,hGrid);
    const split=splitName(t-start,counts);
    const row={date:draws[t].date,cutoff:draws[t-1].date,split,index:t,trainingPairs:pred.trainingPairs,previousDraw:draws[t-1].nums.join(" "),...score};
    rows.push(row);
    const f=[row.date,row.cutoff,split,t,pred.trainingPairs,row.previousDraw,fmt(row.brierNull),...row.brierModel.map(fmt),row.top5NullHits,...row.top5ModelHits,row.p5BrierNull===undefined?"":fmt(row.p5BrierNull),fmt(row.p5BrierFull[3]),fmt(row.p5BrierOnly),row.p5Top5NullHits,row.p5Top5Full[3],row.p5Top5Only];
    ledgerLines.push(f.join(","));
  }
  const discovery=rows.slice(0,counts.discovery);
  const validation=rows.slice(counts.discovery,counts.discovery+counts.validation);
  const blind=rows.slice(counts.discovery+counts.validation);
  const splitResults={discovery:summarizeSplit(discovery,hGrid),validation:summarizeSplit(validation,hGrid),blind_oos_historical:summarizeSplit(blind,hGrid)};
  const selectedH=hGrid.map((h,k)=>({h,brier:mean(validation.map(r=>r.brierModel[k]))})).sort((a,b)=>a.brier-b.brier || b.h-a.h)[0].h;
  const selectedIndex=hGrid.indexOf(selectedH);
  const tests=[];
  for(let k=0;k<hGrid.length;k++) {
    tests.push({id:"h="+hGrid[k]+"|brier_gain",bandwidth:hGrid[k],endpoint:"brier_gain_vs_exact_prior",values:blind.map(r=>r.brierNull-r.brierModel[k])});
    tests.push({id:"h="+hGrid[k]+"|top5_gain",bandwidth:hGrid[k],endpoint:"top5_hit_gain_vs_exact_prior",values:blind.map(r=>r.top5ModelHits[k]-r.top5NullHits)});
  }
  const inference=inferFamily(tests,BLOCK_LENGTH,protocol.inference.circular_block_bootstrap_replicates,protocol.inference.block_signflip_replicates,protocol.inference.random_seed_bootstrap,protocol.inference.random_seed_signflip);
  const inferenceRows=inference.map(x=>({id:x.id,bandwidth:x.bandwidth,endpoint:x.endpoint,mean_gain:x.mean,block_bootstrap_ci95:x.ci95,block_signflip_p_one_sided:x.p_raw,holm_adjusted_p:x.p_holm,block_count:x.block_count,n:blind.length}));
  const selectedInference=inferenceRows.filter(x=>x.bandwidth===selectedH);
  const valGain=splitResults.validation.full_state_kernel[String(selectedH)].mean_brier_gain_vs_exact_prior;
  const blindGain=splitResults.blind_oos_historical.full_state_kernel[String(selectedH)].mean_brier_gain_vs_exact_prior;
  const blindBrierTest=selectedInference.find(x=>x.endpoint==="brier_gain_vs_exact_prior");
  const primaryMet=valGain>0 && blindGain>0 && blindBrierTest.holm_adjusted_p<0.05;
  const p5Diag=mean(blind.map(r=>r.p5BrierOnly-r.p5BrierFull[selectedIndex]));
  const p5Top5Diag=mean(blind.map(r=>r.p5Top5Full[selectedIndex]-r.p5Top5Only));
  const report={
    experiment_id:protocol.experiment_id,
    generated_at_utc:"2026-11-10",
    status:"HISTORICAL_EXPLORATORY_COMPLETE",
    validation_status:primaryMet?"HISTORICAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION":"NO_PREDICTIVE_LIFT_DEMONSTRATED",
    question:protocol.question,
    hypothesis:protocol.hypothesis,
    source:{path:protocol.source.path,git_blob_sha1:protocol.source.git_blob_sha1,draws:draws.length,first_date:draws[0].date,last_date:draws[draws.length-1].date,target_count:rows.length,first_target:rows[0].date,last_target:rows[rows.length-1].date},
    method:{state:"five previous sorted positions standardized by exact order-statistic means and SDs",distance:"mean squared standardized Euclidean distance across five positions",kernel:"exp(-d2/(2*h^2))",bandwidth_grid:hGrid,alpha,training_pairs:"historical transitions u=1..t-1, state draw[u-1], outcome draw[u]",p5_only_comparator:"one-dimensional standardized P5 kernel, fixed h=1.5 and alpha=200",target_start_index:start},
    splits:{discovery:counts.discovery,validation:counts.validation,blind_oos_historical:counts.blind_oos_historical},
    validation_selection:{selected_bandwidth:selectedH,criterion:"lowest mean five-position multiclass Brier on Validation; tie-break larger h",validation_gain_vs_exact_prior:valGain},
    split_results:splitResults,
    blind_inference:{primary_endpoint:"paired mean multiclass Brier gain vs exact order-statistic prior; positive favors full-state kernel",tests:inferenceRows,family_size:inferenceRows.length,multiple_testing:"Holm across 4 bandwidths x 2 endpoints (8 tests)",block_length:BLOCK_LENGTH,bootstrap_replicates:protocol.inference.circular_block_bootstrap_replicates,signflip_replicates:protocol.inference.block_signflip_replicates,selected_bandwidth_primary_test:blindBrierTest},
    selected_model_diagnostics:{selected_bandwidth:selectedH,blind_brier_gain_vs_exact_prior:blindGain,blind_p5_brier_gain_full_vs_fixed_p5_only:roundN(p5Diag),blind_p5_top5_hit_gain_full_vs_fixed_p5_only:roundN(p5Top5Diag),interpretation:"Descriptive comparator only; not part of the preregistered 8-test Holm family."},
    integrity:{archive_rows:draws.length,strict_prior_cutoff_checks:strictChecks,all_training_outcomes_strictly_before_target:true,missing_targets:0,all_dates_unique_and_increasing:true,all_draws_valid_sorted_5_of_40:true,probability_normalization_checks:normalizationChecks,max_probability_sum_error:roundN(maxNormError,12),exact_prior_mass_max_error:roundN(Math.max(...priors.map(p=>Math.abs(p.mass-1))),12),synthetic_tests:selfTests},
    decision:{primary_gate:primaryMet?"HISTORICAL_GATE_MET_BUT_PROSPECTIVE_CONFIRMATION_REQUIRED":"NOT_MET",research_only:true,merge_allowed:false,production_change_allowed:false,promotion_allowed:false,human_review_required:true},
    limitations:protocol.limitations_preregistered.concat(["This is a marginal-position model, not a joint quintet probability model.","The full-state kernel and P5-only diagnostic share the same training archive and shrinkage prior.","Historical Discovery/Validation/Blind splits are not a prospective trial; Blind OOS has prior SONAR exposure.","The one-sided block sign-flip is Monte Carlo and depends on exchangeability of contiguous 20-target block signs."]),
    next_action:"Do not tune this historical model further. Continue Q60 append-only prospective collection; only if a future independently preregistered trial is justified should this fixed model be frozen prospectively."
  };
  const ledger=ledgerLines.join("\n")+"\n";
  const reportText=JSON.stringify(report,null,2)+"\n";
  return {report,reportText,ledger,ledgerChars:ledger.length,reportChars:reportText.length,rows:rows.length};
}

function main() {
  const csv=fs.readFileSync("data/storico_daily.csv","utf8");
  const protocolText=fs.readFileSync(PROTOCOL_PATH,"utf8");
  const protocol=JSON.parse(protocolText);
  const gitBlobSha1=(value)=>{const b=Buffer.from(value,"utf8");return crypto.createHash("sha1").update(Buffer.from("blob "+b.length+"\\0")).update(b).digest("hex");};
  assert(gitBlobSha1(csv)===protocol.source.git_blob_sha1,"canonical archive Git blob SHA mismatch");
  assert(gitBlobSha1(protocolText)==="883226aeb8d54dedf8f015d72c2d06e12cae349c","preregistered protocol Git blob SHA mismatch");
  const out=runExperiment(csv,protocol);
  if(process.argv.includes("--verify")) {
    const report=fs.readFileSync(REPORT_PATH,"utf8");
    const ledger=fs.readFileSync(LEDGER_PATH,"utf8");
    assert(report===out.reportText,"persisted Q98 report differs from deterministic replay");
    assert(ledger===out.ledger,"persisted Q98 ledger differs from deterministic replay");
    console.log(JSON.stringify({status:"Q98_EXACT_REPLAY_PASS",targets:out.rows,report_chars:out.reportChars,ledger_chars:out.ledgerChars,synthetic_tests:out.report.integrity.synthetic_tests.passed}));
  } else {
    fs.writeFileSync(REPORT_PATH,out.reportText);
    fs.writeFileSync(LEDGER_PATH,out.ledger);
    console.log(JSON.stringify({status:"Q98_OUTPUTS_WRITTEN",targets:out.rows,report_chars:out.reportChars,ledger_chars:out.ledgerChars}));
  }
}
main();
