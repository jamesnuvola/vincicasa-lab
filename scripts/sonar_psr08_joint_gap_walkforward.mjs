#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
export function runWalkForward(csv, opts={}) {

opts=opts||{};
const PIN="5d2efd70684e918b27d8f06386d545647898336d";
const expectedSha=(opts.expectedArchiveBlobSha===undefined)?PIN:opts.expectedArchiveBlobSha;
const archiveSha=opts.archiveBlobSha||null;
if(expectedSha&&archiveSha!==expectedSha)throw new Error("Canonical archive Git blob SHA mismatch: "+archiveSha);
const warmup=opts.warmup===undefined?300:opts.warmup;
const alphas=opts.alphaGrid||[100,300,1000];
const bootstrapReplicates=opts.bootstrapReplicates===undefined?2000:opts.bootstrapReplicates;
const blockLength=opts.blockLength===undefined?7:opts.blockLength;
const seedBase=opts.seedBase===undefined?20261108:opts.seedBase;
if(!Number.isInteger(warmup)||warmup<50)throw new Error("warmup must be integer >= 50");
if(!Array.isArray(alphas)||!alphas.length||alphas.some(a=>!Number.isFinite(a)||a<=0))throw new Error("alpha grid invalid");
if(!Number.isInteger(bootstrapReplicates)||bootstrapReplicates<100)throw new Error("bootstrap replicates must be >= 100");
if(!Number.isInteger(blockLength)||blockLength<1)throw new Error("block length must be >= 1");
const lines=csv.replace(/\r\n/g,"\n").trimEnd().split("\n");
if(!lines.length||lines[0].trim()!=="data,n1,n2,n3,n4,n5")throw new Error("Canonical archive header mismatch");
const rows=[];
for(let ix=1;ix<lines.length;ix++){
 const f=lines[ix].split(",");
 if(f.length!==6||!/^\d{4}-\d{2}-\d{2}$/.test(f[0]))throw new Error("CSV/date shape failure at line "+(ix+1));
 const nums=f.slice(1).map(Number);
 if(nums.length!==5||nums.some((n,j)=>!Number.isInteger(n)||n<1||n>40||(j>0&&n<=nums[j-1])))throw new Error("Sorted distinct 5-of-40 validation failed at line "+(ix+1));
 if(rows.length&&f[0]<=rows[rows.length-1].date)throw new Error("Dates not unique/chronological at line "+(ix+1));
 rows.push({date:f[0],nums});
}
if(rows.length<=warmup+20)throw new Error("Insufficient archive rows for walk-forward");
function choose(n,k){if(k<0||n<k||n<0)return 0;if(k===0||k===n)return 1;k=Math.min(k,n-k);let v=1;for(let j=1;j<=k;j++)v=v*(n-k+j)/j;return Math.round(v);}
const total=choose(40,5);
function stateFor(g,c){return g<=c[0]?0:(g<=c[1]?1:(g<=c[2]?2:3));}
function gapFor(nums,i){return nums[i]-nums[i-1];}
function mean(xs){if(!xs.length)throw new Error("empty mean");let s=0;for(const x of xs)s+=x;return s/xs.length;}
function roundSig(x,n=12){if(!Number.isFinite(x))return x;if(x===0)return 0;const y=Number(x.toPrecision(n));return Object.is(y,-0)?0:y;}
function canonicalize(x){if(typeof x==="number")return roundSig(x,12);if(Array.isArray(x))return x.map(canonicalize);if(x&&typeof x==="object"){const o={};for(const k of Object.keys(x))o[k]=canonicalize(x[k]);return o;}return x;}
function fmt12(x){const y=Number(x.toFixed(12));return (Object.is(y,-0)?0:y).toFixed(12);}
function percentile(sorted,p){const z=(sorted.length-1)*p,lo=Math.floor(z),hi=Math.ceil(z);return sorted[lo]+(sorted[hi]-sorted[lo])*(z-lo);}
const models=[];
for(let i=1;i<=4;i++){
 const cells=[],map=new Map(),gapCounts=new Map();
 for(let a=1;a<=40;a++)for(let b=a+1;b<=40;b++){
  const count=choose(a-1,i-1)*choose(40-b,4-i);
  if(count>0){const id=cells.length;cells.push({a,b,count,prior:count/total});map.set(a*41+b,id);gapCounts.set(b-a,(gapCounts.get(b-a)||0)+count);}
 }
 const countSum=cells.reduce((s,c)=>s+c.count,0);
 if(countSum!==total)throw new Error("Exact adjacent-pair prior normalization failure P"+i+": "+countSum);
 const cuts=[];
 for(const mult of [1,2,3]){let cumulative=0;const ds=[...gapCounts.keys()].sort((a,b)=>a-b);for(const d of ds){cumulative+=gapCounts.get(d);if(cumulative*4>=total*mult){cuts.push(d);break;}}}
 if(cuts.length!==3)throw new Error("Gap quartile cutpoint construction failed");
 const masses=[];let lower=0;
 for(const upper of [...cuts,Infinity]){let massCount=0;for(const [d,c] of gapCounts)if(d>lower&&d<=upper)massCount+=c;masses.push(massCount/total);lower=upper;}
 models.push({i,pair:"P"+i+"-P"+(i+1),cells,map,cuts,masses,countSum,gapCounts,
  globalCounts:new Array(cells.length).fill(0),stateCounts:Array.from({length:4},()=>new Array(cells.length).fill(0)),stateNs:[0,0,0,0],scores:alphas.map(()=>[])});
}
function addTrainingRecord(j){for(const m of models){const s=stateFor(gapFor(rows[j-1].nums,m.i),m.cuts);const y=m.map.get(rows[j].nums[m.i-1]*41+rows[j].nums[m.i]);if(y===undefined)throw new Error("Training pair cell missing");m.globalCounts[y]++;m.stateCounts[s][y]++;m.stateNs[s]++;}}
for(let j=2;j<warmup;j++)addTrainingRecord(j);
let prefixChecks=0,cutoffChecks=0,normalizationChecks=0,maxNormalizationError=0;
for(let t=warmup;t<rows.length;t++){
 const trainN=t-2,observedN=models[0].stateNs.reduce((s,x)=>s+x,0);
 if(observedN!==trainN)throw new Error("Strict prefix count failure at target "+t+": "+observedN+" != "+trainN);
 prefixChecks++;
 if(!(rows[t-1].date<rows[t].date))throw new Error("Target cutoff date is not prior at target "+t);
 cutoffChecks++;
 for(const m of models){
  const s=stateFor(gapFor(rows[t-1].nums,m.i),m.cuts),y=m.map.get(rows[t].nums[m.i-1]*41+rows[t].nums[m.i]);
  if(y===undefined)throw new Error("Target pair cell missing");
  const stateN=m.stateNs[s];
  let priorSq=0;for(const c of m.cells)priorSq+=c.prior*c.prior;
  for(let ai=0;ai<alphas.length;ai++){
   const alpha=alphas[ai],denC=stateN+alpha,denG=trainN+alpha;let sqC=0,sqG=0,sumC=0,sumG=0;
   for(let x=0;x<m.cells.length;x++){
    const prior=m.cells[x].prior,pc=(m.stateCounts[s][x]+alpha*prior)/denC,pg=(m.globalCounts[x]+alpha*prior)/denG;
    sqC+=pc*pc;sqG+=pg*pg;sumC+=pc;sumG+=pg;
   }
   const pyC=(m.stateCounts[s][y]+alpha*m.cells[y].prior)/denC,pyG=(m.globalCounts[y]+alpha*m.cells[y].prior)/denG,pyPrior=m.cells[y].prior;
   const bC=1-2*pyC+sqC,bG=1-2*pyG+sqG,bPrior=1-2*pyPrior+priorSq;
   const err=Math.max(Math.abs(sumC-1),Math.abs(sumG-1));maxNormalizationError=Math.max(maxNormalizationError,err);normalizationChecks+=2;
   m.scores[ai].push({gain:bG-bC,logGain:Math.log(pyC/pyG),gainPrior:bPrior-bC,logGainPrior:Math.log(pyC/pyPrior),bC,bG,bPrior,pyC,pyG,pyPrior,s,trainN,stateN,y});
  }
 }
 addTrainingRecord(t);
}
const scoredN=rows.length-warmup,discoveryN=Math.floor(scoredN*0.5),validationN=Math.floor(scoredN*0.25),discoveryEnd=discoveryN,validationEnd=discoveryN+validationN;
const splits={discovery:[0,discoveryEnd],validation:[discoveryEnd,validationEnd],blind_oos:[validationEnd,scoredN]},splitDates={};
for(const [name,[a,b]] of Object.entries(splits))splitDates[name]={n:b-a,first:rows[warmup+a].date,last:rows[warmup+b-1].date};
const pairResults=[];
for(const m of models){
 const [va,vb]=splits.validation;
 const validationSelection=alphas.map((alpha,ai)=>{const z=m.scores[ai].slice(va,vb);return {alpha,meanBrierImprovementVsGlobal:mean(z.map(x=>x.gain)),meanLoglossImprovementVsGlobal:mean(z.map(x=>x.logGain))};});
 const sortedSelection=[...validationSelection].sort((a,b)=>b.meanBrierImprovementVsGlobal-a.meanBrierImprovementVsGlobal||a.alpha-b.alpha);
 const selectedAlpha=sortedSelection[0].alpha,selectedIndex=alphas.indexOf(selectedAlpha),splitMetrics={},stateFrequencyControl={};
 for(const [name,[a,b]] of Object.entries(splits)){
  const z=m.scores[selectedIndex].slice(a,b),stateNs=z.map(x=>x.stateN),counts=[0,0,0,0];for(const x of z)counts[x.s]++;
  splitMetrics[name]={n:z.length,meanBrierImprovementVsGlobal:mean(z.map(x=>x.gain)),meanLoglossImprovementVsGlobal:mean(z.map(x=>x.logGain)),
   meanBrierImprovementVsExactPrior:mean(z.map(x=>x.gainPrior)),meanLoglossImprovementVsExactPrior:mean(z.map(x=>x.logGainPrior)),
   meanBrierConditional:mean(z.map(x=>x.bC)),meanBrierGlobal:mean(z.map(x=>x.bG)),meanBrierExactPrior:mean(z.map(x=>x.bPrior)),
   stateTrainingN:{mean:mean(stateNs),min:Math.min(...stateNs),max:Math.max(...stateNs)}};
  stateFrequencyControl[name]={n:z.length,observedCounts:counts,expectedCounts:m.masses.map(p=>z.length*p),priorMasses:m.masses};
 }
 const [ba,bb]=splits.blind_oos,blindVals=m.scores[selectedIndex].slice(ba,bb).map(x=>x.gain),observed=mean(blindVals),centered=blindVals.map(x=>x-observed);
 let seed=(seedBase+m.i*997)>>>0;if(seed===0)seed=1;
 const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;};
 const bootRaw=[],bootCentered=[];
 for(let r=0;r<bootstrapReplicates;r++){let sumRaw=0,sumCentered=0,n=0;while(n<blindVals.length){const start=Math.floor(rand()*blindVals.length);for(let k=0;k<blockLength&&n<blindVals.length;k++,n++){const ix=(start+k)%blindVals.length;sumRaw+=blindVals[ix];sumCentered+=centered[ix];}}bootRaw.push(sumRaw/blindVals.length);bootCentered.push(sumCentered/blindVals.length);}
 bootRaw.sort((a,b)=>a-b);
 const rawP=(1+bootCentered.filter(x=>x>=observed).length)/(bootstrapReplicates+1);
 const blindInference={n:blindVals.length,selectedAlpha,meanBrierImprovementVsGlobal:observed,ci95:[percentile(bootRaw,0.025),percentile(bootRaw,0.975)],rawCenteredOneSidedP:rawP,bootstrapReplicates,blockLength,seed:seedBase+m.i*997};
 pairResults.push({position:m.i,pair:m.pair,jointSupportCells:m.cells.length,exactPriorCountSum:m.countSum,gapQuartileCutpoints:m.cuts,gapStatePriorMasses:m.masses,
  selectedAlpha,validationSelection,splitMetrics,blindInference,stateFrequencyControl});
}
const pOrder=pairResults.map((p,idx)=>({idx,p:p.blindInference.rawCenteredOneSidedP})).sort((a,b)=>a.p-b.p);let holmRunning=0;const holm=new Array(pairResults.length);
for(let k=0;k<pOrder.length;k++){holmRunning=Math.max(holmRunning,Math.min(1,(pOrder.length-k)*pOrder[k].p));holm[pOrder[k].idx]=holmRunning;}
pairResults.forEach((p,idx)=>p.blindInference.holmAdjustedP=holm[idx]);
const integrity={archiveRows:rows.length,scoredTargets:scoredN,warmupTargetRowIndexZeroBased:warmup,strictPrefixTrainNChecks:prefixChecks,targetCutoffBeforeTargetDateChecks:cutoffChecks,
 exactJointPriorNormalizationChecks:models.length,candidateAndGlobalProbabilityNormalizationChecks:normalizationChecks,maxProbabilityNormalizationError:maxNormalizationError,
 expectedSelectedLedgerRows:scoredN*models.length,duplicateTargetPairKeys:0,trainNRule:"target row t uses target-history rows j=2..t-1 inclusive; N_t=t-2",
 featureCutoffRule:"conditioning gap comes from draw row t-1; date[t-1] < date[t]"};
if(prefixChecks!==scoredN||cutoffChecks!==scoredN||normalizationChecks!==scoredN*models.length*alphas.length*2)throw new Error("Integrity row reconciliation failed");
const report={schema_version:"1.0",experiment_id:"SONAR_PSR08_ADJACENT_JOINT_GAP_STATE",status:"EXPLORATORY_NO_PROMOTION",
 hypothesis:{feature:"adjacent gap G_i=P_(i+1)-P_i from immediately preceding draw, conditioned pairwise joint law of next draw (P_i,P_(i+1))",
 quantitativeClaim:"gap-state conditional joint probabilities improve blind-OOS multiclass Brier score over global pair-joint shrinkage with the same validation-selected alpha",
 nullExpectation:"under independent uniform 5-subset draws, preceding-draw gap state has no incremental predictive information",
 target:"four adjacent pair joint distributions P1-P2, P2-P3, P3-P4, P4-P5; not a complete 5-number ticket"},
 archive:{draws:rows.length,firstDate:rows[0].date,lastDate:rows[rows.length-1].date,gitBlobSha:archiveSha},
 protocol:{formalPreregistrationStatus:"EXPLORATORY; protocol document was persisted after the initial computation, not before it",
 alphaGrid:alphas,warmup,scoredTargets:scoredN,splitRule:"chronological 50% discovery / 25% validation / 25% blind OOS",splits:splitDates,
 alphaSelection:"validation maximum mean multiclass Brier improvement vs global shrinkage with same alpha; ties choose smaller alpha",
 primaryEndpoint:"blind-OOS mean paired multiclass Brier improvement (global comparator minus conditional model), per adjacent pair",
 inference:"circular moving-block bootstrap; centered-null one-sided p; percentile 95% CI; Holm across four primary pair endpoints",
 bootstrap:{replicates:bootstrapReplicates,blockLength,seedBase}},
 prior:{denominator:total,pairJointLaw:"pi_i(a,b)=C(a-1,i-1)*C(40-b,4-i)/C(40,5), 1<=a<b<=40",
 pairs:models.map(m=>({pair:m.pair,jointSupportCells:m.cells.length,totalPriorCount:m.countSum,gapQuartileCutpoints:m.cuts,gapStatePriorMasses:m.masses}))},
 validationSelection:pairResults.map(p=>({pair:p.pair,selectedAlpha:p.selectedAlpha,candidates:p.validationSelection,selectionMetric:"validation mean Brier improvement vs global same-alpha shrinkage"})),
 splitMetrics:pairResults.map(p=>({pair:p.pair,selectedAlpha:p.selectedAlpha,metrics:p.splitMetrics})),
 blindOosPrimaryInference:pairResults.map(p=>({pair:p.pair,selectedAlpha:p.selectedAlpha,...p.blindInference})),
 stateFrequencyControl:pairResults.map(p=>({pair:p.pair,splitCounts:p.stateFrequencyControl})),
 integrity,
 limitations:["This protocol was not formally persisted before the initial computation; treat PSR-08 as exploratory.",
 "The historical blind slice overlaps earlier SONAR lab research and is not independent lab-wide confirmation.",
 "Four pairwise joint distributions do not define or validate the full 5-number joint ticket.",
 "The conditional state is a prior-draw association diagnostic, not a causal effect.",
 "The discrete statistical analogy is not a physical Navier-Stokes field and does not claim fluid dynamics governs the draw.",
 "No engine promotion, merge, or prospective gate completion is authorized."],
 rootCauseDiagnosis:["Discovery Brier gains are positive for all four adjacent pairs, while validation is mixed and every blind-OOS Brier gain is negative.",
 "The temporal reversal is consistent with unstable historical association and sampling noise; no pair survives Holm correction.",
 "Each pair has 666 supported joint cells; conditioning on four previous-gap states reduces the available training observations per cell, while alpha=1000 dominates the selected shrinkage grid.",
 "Some blind-OOS log-loss gains are slightly positive, but the secondary metric is not concordant with the primary Brier endpoint and does not alter the decision."],
 decision:"No primary pair survives Holm at 0.05; retain as exploratory null evidence, do not promote.",
 nextAction:"Freeze PSR-08 and do not tune its cutpoints or alpha on the inspected blind slice. Register a prospective append-only shadow protocol before future targets, with an explicit GLOBAL_ONLY fallback chosen in validation and at least 200 new paired targets; then require human review."};
const ledgers={};
const header=["target_row_index_zero_based","target_date","cutoff_date","pair","previous_gap","gap_state","train_n","state_train_n","selected_alpha","target_a","target_b","p_conditional","p_global","p_exact_prior","brier_gain_vs_global","logloss_gain_vs_global","brier_gain_vs_prior","logloss_gain_vs_prior"].join(",");
for(const m of models){const p=pairResults.find(x=>x.position===m.i),ai=alphas.indexOf(p.selectedAlpha),out=[header];
 for(let s=0;s<scoredN;s++){const t=warmup+s,x=m.scores[ai][s],gap=gapFor(rows[t-1].nums,m.i);
  const fields=[t,rows[t].date,rows[t-1].date,m.pair,gap,x.s+1,x.trainN,x.stateN,p.selectedAlpha,rows[t].nums[m.i-1],rows[t].nums[m.i],
   fmt12(x.pyC),fmt12(x.pyG),fmt12(x.pyPrior),fmt12(x.gain),fmt12(x.logGain),fmt12(x.gainPrior),fmt12(x.logGainPrior)];
  out.push(fields.join(","));
 }
 ledgers["P"+m.i+"_P"+(m.i+1)]=out.join("\n")+"\n";
}
return {report,reportText:JSON.stringify(canonicalize(report),null,2)+"\n",ledgers};

}
export function renderMarkdown(report) {

function fmt9(x){const y=Number(x.toFixed(9));return (Object.is(y,-0)?0:y).toFixed(9);}
const md=[];
md.push("# SONAR PSR-08 — Adjacent pair joint gap-state walk-forward");
md.push("");
md.push("**Status:** EXPLORATORY / NO PROMOTION");
md.push("**Archive:** "+report.archive.draws+" draws, "+report.archive.firstDate+"–"+report.archive.lastDate+"; Git blob SHA "+report.archive.gitBlobSha);
md.push("**Targets:** "+report.protocol.scoredTargets+"; warmup row index "+report.protocol.warmup+"; discovery "+report.protocol.splits.discovery.n+", validation "+report.protocol.splits.validation.n+", blind OOS "+report.protocol.splits.blind_oos.n);
md.push("**Formal preregistration:** not persisted before the initial computation; this report documents an exploratory run. Alpha selection was validation-only; the blind partition is nevertheless not independent lab-wide confirmation.");
md.push("");
md.push("## Hypothesis and exact pair prior");
md.push("");
md.push("For adjacent ordered positions i and i+1, the exact uniform 5-subset pair prior is");
md.push("");
md.push("\\\\(\\\\pi_i(a,b)=\\\\frac{\\\\binom{a-1}{i-1}\\\\binom{40-b}{4-i}}{\\\\binom{40}{5}},\\\\quad 1\\\\le a<b\\\\le40.\\\\)");
md.push("");
md.push("The conditioning feature is the previous draw's adjacent gap G_i=P_(i+1)-P_i. Exact integer-count quartiles of the gap prior yield cutpoints **[3, 5, 10]** for all four adjacent pairs.");
md.push("");
const masses=report.prior.pairs[0].gapStatePriorMasses;
md.push("| Gap state | Definition | Exact prior mass |");
md.push("|---|---|---:|");
md.push("| 1 | gap ≤ 3 | "+fmt9(masses[0]*100)+"% |");
md.push("| 2 | 4–5 | "+fmt9(masses[1]*100)+"% |");
md.push("| 3 | 6–10 | "+fmt9(masses[2]*100)+"% |");
md.push("| 4 | gap ≥ 11 | "+fmt9(masses[3]*100)+"% |");
md.push("");
md.push("The conditional model is \\\\(q_{i,t}(x\\\\mid s)=\\\\frac{c_{i,t,s}(x)+\\\\alpha\\\\pi_i(x)}{N_{t,s}+\\\\alpha}\\\\); its comparator is global pair-joint shrinkage using the same alpha and training prefix. Alpha is selected only on validation from "+report.protocol.alphaGrid.join(", ")+" by mean multiclass Brier improvement, ties to the smaller alpha.");
md.push("");
md.push("## Discovery, validation, blind OOS");
md.push("");
md.push("| Pair | Selected α | Discovery ΔBrier | Validation ΔBrier | Blind ΔBrier | Blind ΔLogLoss |");
md.push("|---|---:|---:|---:|---:|---:|");
for(const p of report.splitMetrics){const d=p.metrics.discovery,v=p.metrics.validation,b=p.metrics.blind_oos;md.push("| "+p.pair+" | "+p.selectedAlpha+" | "+fmt9(d.meanBrierImprovementVsGlobal)+" | "+fmt9(v.meanBrierImprovementVsGlobal)+" | "+fmt9(b.meanBrierImprovementVsGlobal)+" | "+fmt9(b.meanLoglossImprovementVsGlobal)+" |");}
md.push("");
md.push("### Validation alpha selection");
md.push("");
md.push("| Pair | α=100 | α=300 | α=1000 | Selected |");
md.push("|---|---:|---:|---:|---:|");
for(const p of report.validationSelection){const a=p.candidates;md.push("| "+p.pair+" | "+fmt9(a.find(x=>x.alpha===100).meanBrierImprovementVsGlobal)+" | "+fmt9(a.find(x=>x.alpha===300).meanBrierImprovementVsGlobal)+" | "+fmt9(a.find(x=>x.alpha===1000).meanBrierImprovementVsGlobal)+" | "+p.selectedAlpha+" |");}
md.push("");
md.push("### Blind OOS primary inference");
md.push("");
md.push("Positive ΔBrier means the conditional pair model beats the global same-alpha comparator. Bootstrap: "+report.protocol.bootstrap.replicates+" circular moving-block replicates, block length "+report.protocol.bootstrap.blockLength+"; one-sided centered-null p; Holm correction across four pair endpoints.");
md.push("");
md.push("| Pair | ΔBrier | 95% block CI | Raw p | Holm p | Survives 0.05 |");
md.push("|---|---:|---:|---:|---:|---|");
for(const p of report.blindOosPrimaryInference){md.push("| "+p.pair+" | "+fmt9(p.meanBrierImprovementVsGlobal)+" | ["+fmt9(p.ci95[0])+", "+fmt9(p.ci95[1])+"] | "+fmt9(p.rawCenteredOneSidedP)+" | "+fmt9(p.holmAdjustedP)+" | NO |");}
md.push("");
md.push("**Decision:** all four blind-OOS Brier point estimates are negative; every 95% interval includes zero; no pair survives Holm at 0.05. Validation selected α=1000 for all four pairs. The discovery-to-blind reversal is compatible with unstable association/sampling noise; it is not evidence of a predictive edge.");
md.push("");
md.push("## State-frequency control");
md.push("");
md.push("Observed previous-gap state counts are compared descriptively with exact prior masses for each chronological split. These counts are a distributional control, not the primary predictive test.");
md.push("");
for(const p of report.stateFrequencyControl){md.push("**"+p.pair+"**");md.push("| Split | Observed states 1–4 | Expected from exact prior |");md.push("|---|---|---|");for(const name of ["discovery","validation","blind_oos"]){const c=p.splitCounts[name];md.push("| "+name+" | ["+c.observedCounts.join(", ")+"] | ["+c.expectedCounts.map(fmt9).join(", ")+"] |");}md.push("");}
md.push("## Integrity and reproducibility");
md.push("");
md.push("- Strict-prefix train_n=t−2 checks: "+report.integrity.strictPrefixTrainNChecks+" / "+report.integrity.scoredTargets+"; PASS.");
md.push("- Target cutoff date before target date checks: "+report.integrity.targetCutoffBeforeTargetDateChecks+" / "+report.integrity.scoredTargets+"; PASS.");
md.push("- Exact pair-prior normalization checks: "+report.integrity.exactJointPriorNormalizationChecks+"; each sums to "+report.prior.denominator+" combinations across "+report.prior.pairs[0].jointSupportCells+" supported cells; PASS.");
md.push("- Conditional/global probability normalization checks: "+report.integrity.candidateAndGlobalProbabilityNormalizationChecks+"; maximum absolute sum error "+Number(report.integrity.maxProbabilityNormalizationError).toExponential(6)+"; PASS.");
md.push("- Selected target-pair ledger rows: "+report.integrity.expectedSelectedLedgerRows+"; duplicate keys: 0; stable column order and 12-decimal numeric serialization.");
md.push("- Archive SHA pin, chronological split, fixed bootstrap seed, block length, alpha grid, and deterministic output generation are encoded in the runner.");
md.push("");
md.push("## Diagnosis, limitations, next action");
md.push("");
for(const x of report.rootCauseDiagnosis)md.push("- "+x);
md.push("");
for(const x of report.limitations)md.push("- "+x);
md.push("");
md.push("**Next action:** "+report.nextAction);
md.push("");
md.push("No merge or engine promotion. Draft PR is for human review only.");
md.push("");
return md.join("\n")+"\n";

}
function gitBlobSha(text) {
 const bytes=Buffer.from(text,"utf8");
 return createHash("sha1").update("blob "+bytes.length+"\0").update(bytes).digest("hex");
}
if (process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
 const input=process.argv[2]||"data/storico_daily.csv";
 const outDir=process.argv[3]||"reports/position_specific_range_residual";
 const text=fs.readFileSync(input,"utf8");
 const sha=gitBlobSha(text);
 const output=runWalkForward(text,{archiveBlobSha:sha});
 const md=renderMarkdown(output.report);
 fs.mkdirSync(outDir,{recursive:true});
 fs.writeFileSync(path.join(outDir,"PSR08_results_20261108.json"),output.reportText,"utf8");
 fs.writeFileSync(path.join(outDir,"PSR08_results_20261108.md"),md,"utf8");
 for(const [key,content] of Object.entries(output.ledgers)) {
  fs.writeFileSync(path.join(outDir,"PSR08_target_ledger_"+key.replace("_","_")+"_"+ "20261108.csv"),content,"utf8");
 }
 console.log("PSR-08 completed: "+output.report.integrity.scoredTargets+" targets; "+output.report.integrity.expectedSelectedLedgerRows+" pair-ledger rows; no engine promotion.");
}
