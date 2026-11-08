import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

function stateReference(){
  const choose=(n,k)=>{if(k<0||k>n)return 0;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
  const counts=Array.from({length:6},(_,r)=>choose(20,r)*choose(20,5-r));
  const total=choose(40,5),bins=[counts[0]+counts[1],counts[2]+counts[3],counts[4]+counts[5]];
  return {law:"Hypergeometric(40,20,5)",exact_r_counts:counts,exact_state_counts:bins,total_combinations:total,state_mass_fractions:bins.map(x=>x/total)};
}
function run(csvText, options={}) {
  const cfg=Object.assign({trainStart:200,targetStart:300,discoveryCount:1400,validationCount:850,alphaGrid:[0,25,50,100,200,500,1000],blockLength:7,signFlipReps:20000,bootstrapReps:2000,seed:20261108,strictArchive:true},options);
  const lines=csvText.trim().split(/\r?\n/);
  if(lines[0]!=="data,n1,n2,n3,n4,n5")throw new Error("Unexpected archive header");
  const dates=[],draws=[];
  for(let i=1;i<lines.length;i++){
    const f=lines[i].split(",");
    if(f.length!==6)throw new Error("Bad CSV row "+i);
    const date=f[0],nums=f.slice(1).map(Number);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date))throw new Error("Bad date "+date);
    if(nums.some(x=>!Number.isInteger(x)||x<1||x>40)||new Set(nums).size!==5)throw new Error("Bad draw at "+date);
    nums.sort((a,b)=>a-b);
    if(dates.length&&date<=dates[dates.length-1])throw new Error("Dates not strictly increasing");
    dates.push(date);draws.push(nums);
  }
  const n=draws.length;
  if(cfg.strictArchive&&(n!==3401||dates[0]!=="2017-07-17"||dates[n-1]!=="2026-11-07"))throw new Error("Canonical archive shape/cutoff mismatch");
  if(cfg.targetStart<cfg.trainStart+100||cfg.targetStart>=n)throw new Error("Invalid warmup target");
  const targetCount=n-cfg.targetStart,discoveryEnd=cfg.discoveryCount,validationEnd=cfg.discoveryCount+cfg.validationCount;
  if(discoveryEnd+cfg.validationCount>=targetCount)throw new Error("Invalid split lengths");
  const choose=(nn,kk)=>{if(kk<0||kk>nn)return 0;kk=Math.min(kk,nn-kk);let v=1;for(let i=1;i<=kk;i++)v=v*(nn-kk+i)/i;return v;};
  const topK=(counts,k)=>Array.from({length:40},(_,i)=>i).sort((a,b)=>counts[b]-counts[a]||a-b).slice(0,k);
  const rankAll=(probs)=>{const order=Array.from({length:40},(_,i)=>i).sort((a,b)=>probs[b]-probs[a]||a-b);const rank=new Int16Array(40);for(let i=0;i<40;i++)rank[order[i]]=i+1;return {order:order.map(x=>x+1),rank};};
  const states=new Int8Array(n),overlaps=new Int8Array(n),top20ForTarget=new Array(n);
  let scoredStateWindowChecks=0;
  for(let t=cfg.trainStart;t<n;t++){
    const start=t-101,end=t-2;
    if(start<0||end>=t-1||end-start+1!==100)throw new Error("State window cutoff failure at "+t);
    const counts=new Int32Array(40);
    for(let j=start;j<=end;j++)for(const v of draws[j])counts[v-1]++;
    const top20=topK(counts,20),set=new Set(top20);let r=0;
    for(const v of draws[t-1])if(set.has(v-1))r++;
    overlaps[t]=r;states[t]=r<=1?0:r<=3?1:2;top20ForTarget[t]=top20.map(x=>x+1);
    if(t>=cfg.targetStart)scoredStateWindowChecks++;
  }
  const globalCounts=new Float64Array(40),stateCounts=[new Float64Array(40),new Float64Array(40),new Float64Array(40)],stateExposure=[0,0,0];
  for(let u=cfg.trainStart;u<cfg.targetStart;u++){for(const v of draws[u])globalCounts[v-1]++;const s=states[u];stateExposure[s]++;for(const v of draws[u])stateCounts[s][v-1]++;}
  const records=cfg.alphaGrid.map(()=>[]),globalRecords=[],selectedTargetStates=[0,0,0];
  let normalizationChecks=0,maxProbabilitySumError=0,cutoffChecks=0,prefixChecks=0;
  const verifyProb=probs=>{const sum=probs.reduce((a,b)=>a+b,0),error=Math.abs(sum-5);normalizationChecks++;maxProbabilitySumError=Math.max(maxProbabilitySumError,error);if(error>1e-12)throw new Error("Inclusion probability vector normalization failure: "+error);};
  const addOutcome=u=>{for(const v of draws[u])globalCounts[v-1]++;const s=states[u];stateExposure[s]++;for(const v of draws[u])stateCounts[s][v-1]++;};
  const score=(probs,actual)=>{
    const ranked=rankAll(probs),actualSet=new Set(actual);let h5=0,h10=0,h20=0,rankSum=0,brier=0,ll=0;
    for(let n0=0;n0<40;n0++){const y=actualSet.has(n0+1)?1:0,p=Math.max(1e-12,Math.min(1-1e-12,probs[n0]));const e=p-y;brier+=e*e;ll-=y*Math.log(p)+(1-y)*Math.log(1-p);}
    for(const v of actual){const r=ranked.rank[v-1];rankSum+=r;if(r<=5)h5++;if(r<=10)h10++;if(r<=20)h20++;}
    return {hits5:h5,hits10:h10,hits20:h20,meanRank:rankSum/5,brier:brier/40,logLoss:ll/40,top5:ranked.order.slice(0,5),top10:ranked.order.slice(0,10),top20:ranked.order.slice(0,20)};
  };
  for(let t=cfg.targetStart;t<n;t++){
    const s=states[t],ns=stateExposure[s],ng=t-cfg.trainStart;
    if(ng!==t-cfg.trainStart)throw new Error("Training prefix mismatch at "+t);
    if(dates[t-1]>=dates[t])throw new Error("Target cutoff is not prior at "+t);
    cutoffChecks++;prefixChecks++;
    const q0=Array.from(globalCounts,x=>x/ng);verifyProb(q0);
    const base=score(q0,draws[t]);
    globalRecords.push({date:dates[t],cutoff:dates[t-1],state:s,overlap:overlaps[t],priorTop20:top20ForTarget[t],trainN:ng,stateN:ns,actual:draws[t].join(" "),...base});
    selectedTargetStates[s]++;
    for(let ai=0;ai<cfg.alphaGrid.length;ai++){
      const alpha=cfg.alphaGrid[ai],denom=ns+alpha;
      const probs=Array.from({length:40},(_,j)=>denom===0?q0[j]:(stateCounts[s][j]+alpha*q0[j])/denom);verifyProb(probs);
      const m=score(probs,draws[t]);
      records[ai].push({date:dates[t],cutoff:dates[t-1],state:s,overlap:overlaps[t],priorTop20:top20ForTarget[t],trainN:ng,stateN:ns,alpha,actual:draws[t].join(" "),...m,globalHits5:base.hits5,globalBrier:base.brier,globalLogLoss:base.logLoss,globalTop5:base.top5});
    }
    addOutcome(t);
  }
  const round9=x=>{const y=Math.round((x+Number.EPSILON)*1e9)/1e9;return Object.is(y,-0)?0:y;};
  const summarize=(arr,from,to)=>{
    const sub=arr.slice(from,to),nn=sub.length;if(!nn)return null;
    const sums={hits5:0,hits10:0,hits20:0,meanRank:0,brier:0,logLoss:0,globalHits5:0,globalBrier:0,globalLogLoss:0};
    for(const r of sub)for(const k of Object.keys(sums))sums[k]+=r[k];
    return {targets:nn,top5Hits:sums.hits5,top5HitSharePct:round9(sums.hits5/(nn*5)*100),top10CoveragePct:round9(sums.hits10/(nn*5)*100),top20CoveragePct:round9(sums.hits20/(nn*5)*100),meanRank:round9(sums.meanRank/nn),brier:round9(sums.brier/nn),logLoss:round9(sums.logLoss/nn),globalTop5Hits:sums.globalHits5,globalTop5HitSharePct:round9(sums.globalHits5/(nn*5)*100),globalBrier:round9(sums.globalBrier/nn),globalLogLoss:round9(sums.globalLogLoss/nn),deltaTop5HitSharePp:round9((sums.hits5-sums.globalHits5)/(nn*5)*100),brierGain:round9((sums.globalBrier-sums.brier)/nn),logLossGain:round9((sums.globalLogLoss-sums.logLoss)/nn)};
  };
  const summarizeBase=(arr,from,to)=>{
    const sub=arr.slice(from,to),nn=sub.length;if(!nn)return null;
    let h5=0,h10=0,h20=0,mr=0,br=0,ll=0;
    for(const r of sub){h5+=r.hits5;h10+=r.hits10;h20+=r.hits20;mr+=r.meanRank;br+=r.brier;ll+=r.logLoss;}
    return {targets:nn,top5Hits:h5,top5HitSharePct:round9(h5/(nn*5)*100),top10CoveragePct:round9(h10/(nn*5)*100),top20CoveragePct:round9(h20/(nn*5)*100),meanRank:round9(mr/nn),brier:round9(br/nn),logLoss:round9(ll/nn)};
  };
  const splitMetrics=cfg.alphaGrid.map((alpha,ai)=>({alpha,discovery:summarize(records[ai],0,discoveryEnd),validation:summarize(records[ai],discoveryEnd,validationEnd),blindOos:summarize(records[ai],validationEnd,targetCount)}));
  let best=0;
  for(let ai=1;ai<cfg.alphaGrid.length;ai++){const a=splitMetrics[ai].validation,b=splitMetrics[best].validation;if(a.top5Hits>b.top5Hits||(a.top5Hits===b.top5Hits&&(a.brier<b.brier||(a.brier===b.brier&&cfg.alphaGrid[ai]>cfg.alphaGrid[best]))))best=ai;}
  const blindStart=validationEnd,blind=records.map(a=>a.slice(blindStart,targetCount)),blindGlobal=globalRecords.slice(blindStart,targetCount);
  const hyperPmf=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/choose(40,5));
  let uniformDist=new Float64Array((targetCount-validationEnd)*5+1);uniformDist[0]=1;
  for(let i=0;i<blindGlobal.length;i++){const old=uniformDist,lim=i*5,newDist=new Float64Array((i+1)*5+1);for(let h=0;h<=lim;h++)if(old[h]!==0)for(let k=0;k<=5;k++)newDist[h+k]+=old[h]*hyperPmf[k];uniformDist.set(newDist);}
  const exactTail=obs=>{let p=0;for(let h=obs;h<uniformDist.length;h++)p+=uniformDist[h];return Math.max(0,Math.min(1,p));};
  const blockLength=cfg.blockLength,completeN=Math.floor(blindGlobal.length/blockLength)*blockLength,blockCount=completeN/blockLength,tailOmitted=blindGlobal.length-completeN;
  const xorshift=seed=>{let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return x>>>0;};};
  const signFlipP=(values,reps,seed)=>{const sums=[];for(let b=0;b<blockCount;b++){let s=0;for(let j=0;j<blockLength;j++)s+=values[b*blockLength+j];sums.push(s);}const observed=sums.reduce((a,b)=>a+b,0),rand=xorshift(seed);let ge=0;for(let r=0;r<reps;r++){let stat=0;for(const s of sums)stat+=(rand()&1)?s:-s;if(stat>=observed-1e-14)ge++;}return {p:(ge+1)/(reps+1),observedSum:observed,completeTargets:completeN,blocks:blockCount,tailOmitted};};
  const testRows=[],inferByAlpha=[];
  for(let ai=0;ai<cfg.alphaGrid.length;ai++){
    const arr=blind[ai],obsHits=arr.reduce((a,r)=>a+r.hits5,0),dTop=arr.map((r,j)=>r.hits5-blindGlobal[j].hits5),dBrier=arr.map((r,j)=>blindGlobal[j].brier-r.brier);
    const pUniform=exactTail(obsHits),pTop=signFlipP(dTop,cfg.signFlipReps,cfg.seed+1000+ai*17),pBri=signFlipP(dBrier,cfg.signFlipReps,cfg.seed+2000+ai*17);
    const row={alpha:cfg.alphaGrid[ai],blindTop5Hits:obsHits,blindTop5HitSharePct:round9(obsHits/(arr.length*5)*100),globalTop5Hits:arr.reduce((a,r)=>a+r.globalHits5,0),globalTop5HitSharePct:round9(arr.reduce((a,r)=>a+r.globalHits5,0)/(arr.length*5)*100),deltaTop5HitSharePp:round9(dTop.reduce((a,b)=>a+b,0)/(arr.length*5)*100),brier:round9(arr.reduce((a,r)=>a+r.brier,0)/arr.length),globalBrier:round9(arr.reduce((a,r)=>a+r.globalBrier,0)/arr.length),brierGain:round9(dBrier.reduce((a,b)=>a+b,0)/arr.length),logLoss:round9(arr.reduce((a,r)=>a+r.logLoss,0)/arr.length),globalLogLoss:round9(arr.reduce((a,r)=>a+r.globalLogLoss,0)/arr.length),logLossGain:round9(arr.reduce((a,r)=>a+r.globalLogLoss-r.logLoss,0)/arr.length),pExactUniformTop5:round9(pUniform),pPairedBlockTop5:round9(pTop.p),pPairedBlockBrier:round9(pBri.p)};
    inferByAlpha.push(row);testRows.push({key:"alpha"+row.alpha+"_uniform_top5",p:round9(pUniform)},{key:"alpha"+row.alpha+"_paired_top5",p:round9(pTop.p)},{key:"alpha"+row.alpha+"_paired_brier",p:round9(pBri.p)});
  }
  const sorted=testRows.slice().sort((a,b)=>a.p-b.p||a.key.localeCompare(b.key));let prev=0;const holm={};
  for(let i=0;i<sorted.length;i++){const adj=Math.max(prev,Math.min(1,(sorted.length-i)*sorted[i].p));prev=adj;holm[sorted[i].key]=round9(adj);}
  for(const r of inferByAlpha){r.pHolmUniformTop5=holm["alpha"+r.alpha+"_uniform_top5"];r.pHolmPairedTop5=holm["alpha"+r.alpha+"_paired_top5"];r.pHolmPairedBrier=holm["alpha"+r.alpha+"_paired_brier"];}
  const selectedAlpha=cfg.alphaGrid[best],selectedBlind=blind[best],selectedDiffTop=selectedBlind.map((r,j)=>r.hits5-blindGlobal[j].hits5),selectedDiffBrier=selectedBlind.map((r,j)=>blindGlobal[j].brier-r.brier);
  const blockSums=vals=>{const out=[];for(let b=0;b<blockCount;b++){let s=0;for(let j=0;j<blockLength;j++)s+=vals[b*blockLength+j];out.push(s);}return out;};
  const bootCI=(vals,reps,seed,multiplier)=>{const sums=blockSums(vals),rand=xorshift(seed),means=[];for(let r=0;r<reps;r++){let total=0;for(let b=0;b<blockCount;b++)total+=sums[rand()%blockCount];means.push(total/completeN*multiplier);}means.sort((a,b)=>a-b);const quant=q=>{const pos=(means.length-1)*q,lo=Math.floor(pos),hi=Math.ceil(pos);return means[lo]+(means[hi]-means[lo])*(pos-lo);};return [round9(quant(.025)),round9(quant(.975))];};
  const selectedInf=inferByAlpha[best],selectedAllTop=selectedDiffTop.reduce((a,b)=>a+b,0)/(blindGlobal.length*5)*100,selectedAllBrier=selectedDiffBrier.reduce((a,b)=>a+b,0)/blindGlobal.length;
  const ciTop=bootCI(selectedDiffTop,cfg.bootstrapReps,cfg.seed+9001,20),ciBrier=bootCI(selectedDiffBrier,cfg.bootstrapReps,cfg.seed+9002,1);
  const stateCountsTarget=[0,0,0];for(let t=cfg.targetStart;t<n;t++)stateCountsTarget[states[t]]++;
  const selectedLedger=[];
  for(let j=0;j<records[best].length;j++){const r=records[best][j];selectedLedger.push([cfg.targetStart+j,r.date,r.cutoff,r.overlap,r.state,r.priorTop20.join(" "),r.trainN,r.stateN,r.alpha,r.top5.join(" "),r.actual,r.hits5,r.hits10,r.hits20,round9(r.meanRank),round9(r.brier),round9(r.logLoss),r.globalTop5.join(" "),r.globalHits5,round9(r.globalBrier),round9(r.globalLogLoss)].join(","));}
  const ledger="target_index,date,cutoff,prev_overlap_top20,state,prior_top20_reference,train_outcomes,state_exposure,alpha,model_top5,actual,hits_top5,hits_top10,hits_top20,mean_rank,brier,log_loss,global_top5,global_hits_top5,global_brier,global_log_loss\n"+selectedLedger.join("\n")+"\n";
  const sr=stateReference();
  const result={schema_version:"1.0",experiment_id:"SONAR_PSR11_PRIOR_TOP20_OVERLAP_STATE",status:"EXPLORATORY_NO_PROMOTION",generated_date:"2026-11-08",
    archive:{source:"data/storico_daily.csv",git_blob_sha:"5d2efd70684e918b27d8f06386d545647898336d",draws:n,first_date:dates[0],last_date:dates[n-1],csv_lines:lines.length},
    hypothesis:{claim:"The previous draw's overlap with a Top-20 frequency set built from the 100 draws before that previous draw conditions next-draw per-number inclusion frequency.",state_definition:"R=|D[t-1] intersect Top20(freq on rows t-101..t-2)|; states R=0..1,2..3,4..5.",formula:"q_cond(n|s)=(C_s(n)+alpha*q_global(n))/(N_s+alpha); q_global(n)=C(n)/N, all counts are outcomes u=200..t-1 only.",candidate:"Top-5 numbers ranked by q_cond; ties ascending number.",limitations:"Marginal inclusion scores do not constitute a coherent joint probability over five-subsets."},
    state_reference:{law:sr.law,exact_r_counts:sr.exact_r_counts,exact_state_counts:sr.exact_state_counts,total_combinations:sr.total_combinations,state_mass_fractions:sr.state_mass_fractions,states:{S0:"R=0..1",S1:"R=2..3",S2:"R=4..5"},target_state_counts:stateCountsTarget},
    design:{target_start_index:cfg.targetStart,train_start_index:cfg.trainStart,target_count:targetCount,split:{discovery:{targets:discoveryEnd,start_date:dates[cfg.targetStart],end_date:dates[cfg.targetStart+discoveryEnd-1]},validation:{targets:cfg.validationCount,start_date:dates[cfg.targetStart+discoveryEnd],end_date:dates[cfg.targetStart+validationEnd-1]},blind_oos:{targets:targetCount-validationEnd,start_date:dates[cfg.targetStart+validationEnd],end_date:dates[n-1]}},alpha_grid:cfg.alphaGrid,selected_alpha:selectedAlpha,selection_rule:"Validation maximum Top5 hits; tie lower Brier rounded 1e-9, then larger alpha.",block_inference:{block_length:blockLength,complete_targets:completeN,blocks:blockCount,tail_omitted:tailOmitted,sign_flip_replicates:cfg.signFlipReps,bootstrap_replicates:cfg.bootstrapReps,seed:cfg.seed,holm_family_size:testRows.length,holm:"one family across 7 alphas × exact-uniform Top5, paired block Top5, paired block Brier."}},
    validation_selection:{selected_alpha:selectedAlpha,grid:splitMetrics.map(x=>({alpha:x.alpha,validation_top5_hits:x.validation.top5Hits,validation_top5_share_pct:x.validation.top5HitSharePct,validation_brier:x.validation.brier,validation_brier_gain:x.validation.brierGain}))},
    split_metrics:{configs:splitMetrics,baseline_global:{discovery:summarizeBase(globalRecords,0,discoveryEnd),validation:summarizeBase(globalRecords,discoveryEnd,validationEnd),blind_oos:summarizeBase(globalRecords,validationEnd,targetCount)}},
    blind_inference:{selected_alpha:selectedAlpha,selected_alpha_result:selectedInf,all_alpha_results:inferByAlpha,selected_delta_top5_share_pp_all_851:round9(selectedAllTop),selected_delta_brier_gain_all_851:round9(selectedAllBrier),selected_delta_top5_share_pp_block_bootstrap_ci95:ciTop,selected_brier_gain_block_bootstrap_ci95:ciBrier,block_inference_note:"Sign-flip tests and bootstrap CIs use 121 complete 7-target blocks (847 targets); four trailing targets are omitted from block inference, but included in descriptive all-851 metrics.",decision:"No promotion unless selected alpha demonstrates a positive, multiplicity-adjusted and robust blind benefit; historical tail is already exposed in prior SONAR work."},
    integrity:{dates_unique_ascending:true,each_draw_five_distinct_1_to_40:true,strict_prior_training_rule:"outcomes u=200..t-1; state for each u computed using draw u-1 and frequency rows u-101..u-2; score target before updating counts.",target_cutoff_checks:cutoffChecks,state_window_checks:scoredStateWindowChecks,training_prefix_checks:prefixChecks,all_target_cutoffs_precede_target:true,normalization_checks:normalizationChecks,normalization_tolerance:1e-12,max_probability_sum_error:maxProbabilitySumError.toExponential(12),ledger_rows:targetCount,ledger_alpha:selectedAlpha},
    diagnosis:{verified_prior_results:["PSR-07: state-conditioned marginals selected by validation show inconsistent position-wise Brier/Top5 gains; blind inference does not confirm robust improvement.","PSR-08: adjacent joint-gap state models have no multiplicity-adjusted blind lift across the four pairs.","PSR-09: position-recency marginal model has no Holm-significant blind endpoint; selected validation parameters do not translate into consistent blind proper-score gains.","PSR-10: previous-draw sum-quartile state marginals show no Holm-significant blind endpoint; P4 blind Brier gain is negative.","FD-03: diffusion grid selected model fails family-wise and matched-RAW paired gates (Holm p=0.2424 for uniform Top5; paired Holm p=1).","FD-04/05/06: P5 order-statistic and Markov/logistic audits do not establish lift; FD-06 logistic Top5 is below numerical P5 reference across discovery, validation and blind.","FD-07: lag-1 bonus candidate has no Holm-significant Top5 lift; selected model raw uniform p=0.22219, Holm p=1; best uncorrected blind grid candidate Holm p=0.66872.","FD-08: selected structural-sum conditioned frequency model has blind Top5 share 12.6439% but Brier 0.111640, worse than the 0.109375 uniform inclusion baseline; the blind-leading configuration was descriptive only and not validation-selected.","FD-09: selected odd-count conditioned frequency model's blind Top5 share is 12.0799% vs 11.5864% unconditional baseline (+0.4935 pp), paired raw p=0.40823/Holm p=1; Brier gain is negative."],root_cause:"Repeated historical state-conditioning and tuning on the same exposed tail risks selection overfit; conditional-state exposures are sparse relative to 40-number outcomes; Top5 point gains are not accompanied by proper-score improvement or independent prospective evidence.",new_hypothesis_reason:"PSR-11 fixes a predictor-specific prior-Top20 overlap state and exact hypergeometric reference masses before computation; validation selects alpha, and all seven alpha configurations are corrected as one family."},
    prospective_context:{canonical_main_gate_complete:20,minimum_required:200,promotion_allowed:false,latest_freeze_target:"2026-11-08",latest_freeze_status:"FROZEN_PENDING",latest_freeze_cutoff:"2026-11-07",missing_freezes_reconstructed:0},
    reproducibility_corrections:["Initial Node 20 exact replay found the Markdown baseline-share renderer used the modulo operator after toFixed(), yielding NaN; corrected to concatenate a literal percent sign and regenerate the report.","Synthetic state-bin assertion was corrected from representative overlap values to the registered threshold mapping R<=1, R<=3, else state 2.","Target-leakage perturbation test now holds alpha=0 fixed because changing a discovery outcome can legitimately affect validation alpha selection through later strict-prior training history; the test isolates target-t self-leakage."],
    next_action:"Freeze PSR-11 as exploratory. Do not tune against the same historical tail again; continue append-only Q60 prospective scoring and register any next feature before new outcomes are observed."};
  const json=JSON.stringify(result,null,2)+"\n";
  const md=[];
  md.push("# VinciCasa SONAR — PSR-11 Prior Top-20 Overlap-State Inclusion Frequency");
  md.push("**Run date:** 2026-11-08 · **Status:** EXPLORATORY / NO PROMOTION");
  md.push("");
  md.push("## Hypothesis and fixed state");
  md.push("The previous draw's overlap R with a Top-20 frequency set built from the 100 draws strictly before it is binned into S0 (R=0–1), S1 (R=2–3), S2 (R=4–5). Conditional per-number inclusion frequency is shrunk toward strict-prior global inclusion frequency: q_cond=(C_s(n)+alpha*q_global(n))/(N_s+alpha). Top-5 candidates are ranked by q_cond; this is not a joint five-subset distribution.");
  md.push("");
  md.push("## Archive and split");
  md.push("- Canonical CSV blob SHA: 5d2efd70684e918b27d8f06386d545647898336d; "+n+" draws through "+dates[n-1]+".");
  md.push("- Walk-forward targets: "+targetCount+"; discovery "+discoveryEnd+", validation "+cfg.validationCount+", blind tail "+(targetCount-validationEnd)+".");
  md.push("- Blind tail: "+result.design.split.blind_oos.start_date+" to "+result.design.split.blind_oos.end_date+"; this tail has already been inspected by earlier SONAR experiments, so it is not independent confirmation.");
  md.push("- Alpha grid: "+cfg.alphaGrid.join(", ")+". Validation-selected alpha="+selectedAlpha+".");
  md.push("");
  md.push("## Discovery / validation / blind OOS");
  md.push("| alpha | Discovery Top5 share | Validation Top5 share | Blind Top5 share | Blind global-frequency baseline | Delta share (pp) | Blind Brier gain |");
  md.push("|---:|---:|---:|---:|---:|---:|");
  for(const x of splitMetrics)md.push("| "+x.alpha+" | "+x.discovery.top5HitSharePct.toFixed(6)+"% | "+x.validation.top5HitSharePct.toFixed(6)+"% | "+x.blindOos.top5HitSharePct.toFixed(6)+"% | "+x.blindOos.globalTop5HitSharePct.toFixed(6)+"% | "+x.blindOos.deltaTop5HitSharePp.toFixed(6)+" | "+x.blindOos.brierGain.toFixed(9)+" |");
  md.push("");
  md.push("## Blind inference across the preregistered alpha family");
  md.push("Holm correction spans 21 tests (7 alpha configurations × exact uniform Top5, paired block Top5 vs strict-prior global frequency, paired block Brier gain vs strict-prior global frequency).");
  md.push("| alpha | Top5 share | Delta vs global (pp) | Brier gain | Exact p | Holm | Paired Top5 p | Holm | Paired Brier p | Holm |");
  md.push("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|");
  for(const r of inferByAlpha)md.push("| "+r.alpha+" | "+r.blindTop5HitSharePct.toFixed(6)+"% | "+r.deltaTop5HitSharePp.toFixed(6)+" | "+r.brierGain.toFixed(9)+" | "+r.pExactUniformTop5.toFixed(6)+" | "+r.pHolmUniformTop5.toFixed(6)+" | "+r.pPairedBlockTop5.toFixed(6)+" | "+r.pHolmPairedTop5.toFixed(6)+" | "+r.pPairedBlockBrier.toFixed(6)+" | "+r.pHolmPairedBrier.toFixed(6)+" |");
  md.push("");
  md.push("## Validation-selected alpha="+selectedAlpha);
  md.push("- Blind Top5: "+selectedInf.blindTop5Hits+" hits / "+(blindGlobal.length*5)+" number slots = "+selectedInf.blindTop5HitSharePct.toFixed(6)+"%; strict-prior global-frequency Top5 baseline "+selectedInf.globalTop5Hits+" hits = "+selectedInf.globalTop5HitSharePct.toFixed(6)+"%.");
  md.push("- Paired Top5 delta vs global baseline: "+selectedInf.deltaTop5HitSharePp.toFixed(6)+" pp; raw block sign-flip p="+selectedInf.pPairedBlockTop5.toFixed(6), " and Holm p="+selectedInf.pHolmPairedTop5.toFixed(6)+".");
  md.push("- Exact uniform Top5 expected share 12.5%; selected model's one-sided exact p="+selectedInf.pExactUniformTop5.toFixed(6)+" (Holm="+selectedInf.pHolmUniformTop5.toFixed(6)+").");
  md.push("- Brier gain vs global frequency: "+selectedInf.brierGain.toFixed(9)+"; raw block sign-flip p="+selectedInf.pPairedBlockBrier.toFixed(6)+" (Holm="+selectedInf.pHolmPairedBrier.toFixed(6)+"). The block-bootstrap 95% CI for Brier gain is ["+ciBrier[0].toFixed(9)+", "+ciBrier[1].toFixed(9)+"] (negative means worse proper score).");
  md.push("- Paired Top5 delta across all 851 blind targets (descriptive): "+result.blind_inference.selected_delta_top5_share_pp_all_851.toFixed(6)+" pp; block-bootstrap 95% CI ["+ciTop[0].toFixed(6)+", "+ciTop[1].toFixed(6)+"] pp.");
  md.push("- Block inference uses 121 complete 7-target blocks (847 targets); four trailing targets are omitted from sign-flip/bootstrap inference but included in descriptive blind metrics.");
  md.push("");
  md.push("## Integrity, reproducibility, and limits");
  md.push("- Archive schema/date/number checks passed; strict-prefix outcomes u=200..t−1 only. Predictor state for each outcome u uses draw u−1 and Top20 frequency rows u−101..u−2, exactly 100 rows and excluding draw u−1 from the ranking window.");
  md.push("- Cutoff/prefix/state-window checks: "+cutoffChecks+"/"+targetCount+" each. Inclusion probability normalization checks: "+normalizationChecks+"; maximum sum-to-5 error "+maxProbabilitySumError.toExponential(12)+" (tolerance 1e-12).");
  md.push("- Exact state masses under uniform 5-of-40: 17.082467%, 65.835066%, 17.082467% (counts 112,404 / 433,200 / 112,404 of 658,008).");
  md.push("- Selected-alpha ledger contains "+targetCount+" target rows, with prior Top20 reference, cutoff, overlap state, exposure, candidate, actual and paired global baseline. Output metrics canonicalized to 9 decimal places.");
  md.push("- Reproducibility QA: Node 20 replay initially exposed a Markdown baseline-share NaN caused by a modulo/percent typo; renderer was corrected. Synthetic state-bin and target-leakage checks were also tightened (threshold mapping and fixed-alpha perturbation).");
  md.push("- Historical blind tail already exposed in prior SONAR work; no independent prospective confirmation, no physical Navier-Stokes mechanism, no shadow insertion, and no engine promotion.");
  md.push("");
  md.push("## Diagnosis and next action");
  md.push("Prior PSR-07–10 and FD-03–09 experiments repeatedly produced small retrospective point gains without multiplicity-adjusted or proper-score stability. PSR-11 selects alpha=0 and has a +0.235018 pp blind Top5 point difference vs global frequency, but paired p=0.362182/Holm=1; its Brier gain is −0.000128867 with a block-bootstrap CI entirely below zero. Freeze PSR-11 as a null/exploratory result; continue the append-only Q60 gate (20/200 complete; 2026-11-08 freeze remains pending) and do not tune the exposed tail again.");
  const markdown=md.join("\n")+"\n";
  return {result,json,markdown,ledger};
}
export { run, stateReference };

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const archiveText = readFileSync(resolve(root, "data/storico_daily.csv"), "utf8");
  const out = run(archiveText);
  const expected = [
    [resolve(root, "reports/position_specific_range_residual/PSR11_results_20261108.json"), out.json],
    [resolve(root, "reports/position_specific_range_residual/PSR11_results_20261108.md"), out.markdown],
    [resolve(root, "reports/position_specific_range_residual/PSR11_target_ledger_selected_alpha_20261108.csv"), out.ledger]
  ];
  if (process.argv.includes("--verify")) {
    for (const [path, content] of expected) {
      const actual = readFileSync(path, "utf8");
      if (actual !== content) throw new Error("Committed PSR-11 replay mismatch: " + path);
    }
    console.log("PSR-11 exact committed-output replay PASS");
  } else {
    for (const [path, content] of expected) writeFileSync(path, content, "utf8");
    console.log("PSR-11 outputs written");
  }
}
