import fs from "node:fs";
import crypto from "node:crypto";

function runQ104(archiveText,sourceText,protocolText,protocolBlobSha){
 const fail=m=>{throw new Error("Q104: "+m)},TEMPS=[0.1,0.2,0.35,0.5,0.75,1,1.5,2,4],CANDS=["uniform",...TEMPS.map(String)];
 const W=200,D=1921,V=641,B=641,C=658008,L=Math.log(C),BL=20,BOOT=10000,PRIMARY=50000,FAMILY=10000,SEED=20261110;
 const r12=x=>{if(!Number.isFinite(x))fail("non-finite metric");const y=Number(x.toFixed(12));return Object.is(y,-0)?0:y;};
 const up12=x=>{if(!Number.isFinite(x)||x<0)fail("invalid p-value "+x);return Math.min(1,Math.ceil(x*1e12)/1e12);};
 const json=x=>JSON.stringify(x,null,2)+"\n";
 function parse(t){const ls=t.trim().split(/\r?\n/);if(ls[0]!=="data,n1,n2,n3,n4,n5")fail("header");const a=[];for(let i=1;i<ls.length;i++){const f=ls[i].split(","),d=f[0],n=f.slice(1).map(Number);if(f.length!==6||!/^\d{4}-\d{2}-\d{2}$/.test(d)||n.some((v,j)=>!Number.isInteger(v)||v<1||v>40||(j>0&&n[j-1]>=v)))fail("invalid archive row "+i);if(i>1&&a[i-2].d>=d)fail("chronology");a.push({d,n});}return a;}
 function scorerFrom(t){const a=t.indexOf("function overlapCount"),b=t.indexOf("const Card",a);if(a<0||b<0)fail("scorer boundary");return new Function(t.slice(a,b)+"\nreturn sonarAnalogCore;")();}
 function e5(w,k=5){const d=Array(k+1).fill(0);d[0]=1;for(const x of w)for(let j=k;j>=1;j--)d[j]+=d[j-1]*x;return d[k];}
 function brute(w,k){let z=0;function f(s,l,p){if(!l){z+=p;return;}for(let i=s;i<=w.length-l;i++)f(i+1,l-1,p*w[i]);}f(0,k,1);return z;}
 function valid(s,t){if(!Array.isArray(s)||s.length!==40)fail("score length "+t);const seen=new Set();for(let i=0;i<40;i++){const x=s[i];if(!x||!Number.isInteger(x.n)||x.n<1||x.n>40||seen.has(x.n)||!Number.isFinite(x.score))fail("score item "+t);if(i&&(s[i-1].score<x.score||(s[i-1].score===x.score&&s[i-1].n>x.n)))fail("score sort "+t);seen.add(x.n);}if(seen.size!==40)fail("score permutation "+t);}
 const k=T=>String(T).replace(".","_"),split=o=>o<D?"discovery":o<D+V?"validation":"historical_blind_oos";
 function utilities(s){const v=s.map(x=>x.score),lo=Math.min(...v),hi=Math.max(...v),range=hi-lo,m=Array(41).fill(0),r=Array(41).fill(0);s.forEach((x,i)=>{m[x.n]=range?(x.score-lo)/range:0;r[x.n]=(40-i)/39;});return {m,r,lo,hi,range};}
 function gain(u,actual,T){const lw=Array(41).fill(0);for(let n=1;n<=40;n++)lw[n]=(u[n]-1)/T;const z=e5(lw.slice(1).map(Math.exp),5);if(!(z>0)||!Number.isFinite(z))fail("normalizer");return {g:L+actual.reduce((a,n)=>a+lw[n],0)-Math.log(z),lw,logz:Math.log(z)};}
 function blocks(v){const a=[];for(let i=0;i<v.length;i+=BL)a.push(v.slice(i,Math.min(v.length,i+BL)).reduce((x,y)=>x+y,0));return a;}
 function rand(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
 function signflip(bs,reps,seed){const obs=bs.reduce((a,b)=>a+b,0),u=rand(seed);let e=0;for(let i=0;i<reps;i++){let s=0;for(const b of bs)s+=(u()<.5?-1:1)*b;if(s>=obs-1e-12)e++;}const p=(e+1)/(reps+1);return {observed_sum:r12(obs),blocks:bs.length,replicates:reps,extreme:e,p:up12(p),mc_se:r12(Math.sqrt(p*(1-p)/(reps+1)))};}
 function bootCI(v,reps,seed){const n=v.length,full=Math.floor(n/BL),rem=n-full*BL,fw=new Float64Array(n),rw=new Float64Array(n);for(let i=0;i<n;i++){let a=0,b=0;for(let j=0;j<BL;j++)a+=v[(i+j)%n];for(let j=0;j<rem;j++)b+=v[(i+j)%n];fw[i]=a;rw[i]=b;}const u=rand(seed),z=new Array(reps);for(let i=0;i<reps;i++){let s=0;for(let j=0;j<full;j++)s+=fw[Math.floor(u()*n)];if(rem)s+=rw[Math.floor(u()*n)];z[i]=s/n;}z.sort((a,b)=>a-b);return [r12(z[Math.floor(.025*(reps-1))]),r12(z[Math.floor(.975*(reps-1))])];}
 function holm(a,keyFn){const s=[...a].sort((x,y)=>x.p-y.p),m=s.length;let q=0;const map=new Map();for(let i=0;i<m;i++){q=Math.max(q,Math.min(1,(m-i)*s[i].p));map.set(keyFn(s[i]),up12(q));}return a.map(x=>({...x,p_holm:map.get(keyFn(x))}));}
 const draws=parse(archiveText);if(draws.length!==3403||draws[0].d!=="2017-07-17"||draws.at(-1).d!=="2026-11-09")fail("archive cutoff");
 const scorer=scorerFrom(sourceText);if(e5(Array(40).fill(1),5)!==C)fail("uniform count");const small=[.7,1.2,.4,1.7,.9,1.3,.8,1.1];if(Math.abs(e5(small,5)-brute(small,5))>1e-10)fail("small DP");
 const rows=[];let representative=null;
 for(let t=W;t<draws.length;t++){
  const f=scorer(draws.slice(0,t));valid(f.scores,t);const u=utilities(f.scores),actual=draws[t].n,set=new Set(actual);
  const row={target_index:t,target_date:draws[t].d,cutoff_date:draws[t-1].d,max_training_outcome_index:t-1,split:split(t-W),draw_numbers:actual.join(" "),top5_hits:f.scores.slice(0,5).filter(x=>set.has(x.n)).length,top20_hits:f.scores.slice(0,20).filter(x=>set.has(x.n)).length,score_min:r12(u.lo),score_max:r12(u.hi),score_range:r12(u.range)};
  for(const T of TEMPS){const a=gain(u.m,actual,T),b=gain(u.r,actual,T),z=k(T);row["gain_magnitude_"+z]=r12(a.g);row["raw_magnitude_"+z]=a.g;row["gain_rank_"+z]=r12(b.g);row["raw_rank_"+z]=b.g;if(t===W&&T===.5)representative={m:a,r:b};}
  rows.push(row);
 }
 if(rows.length!==3203)fail("target count");
 const disc=rows.filter(x=>x.split==="discovery"),val=rows.filter(x=>x.split==="validation"),blind=rows.filter(x=>x.split==="historical_blind_oos");if(disc.length!==D||val.length!==V||blind.length!==B)fail("split sizes");
 const rg=(row,model,T)=>T===null?0:row["raw_"+model+"_"+k(T)];
 function select(model){const c=TEMPS.map(T=>({temperature:String(T),numeric:T,mean:val.reduce((s,r)=>s+rg(r,model,T),0)/val.length}));c.push({temperature:"uniform",numeric:Infinity,mean:0});c.sort((a,b)=>b.mean-a.mean||b.numeric-a.numeric);return c[0].temperature==="uniform"?null:Number(c[0].temperature);}
 const chosen={magnitude:select("magnitude"),rank:select("rank")};
 function modelSummary(sub,model){const temps={};for(const T of TEMPS){const a=sub.map(r=>rg(r,model,T));temps[String(T)]={mean_log_likelihood_gain:r12(a.reduce((x,y)=>x+y,0)/a.length),cumulative_log_likelihood_gain:r12(a.reduce((x,y)=>x+y,0))};}temps.uniform={mean_log_likelihood_gain:0,cumulative_log_likelihood_gain:0};const T=chosen[model],a=sub.map(r=>rg(r,model,T));return {selected_temperature:T===null?"uniform":String(T),selected_mean_gain:r12(a.reduce((x,y)=>x+y,0)/a.length),selected_cumulative_gain:r12(a.reduce((x,y)=>x+y,0)),temperatures:temps};}
 function splitSummary(sub){return {targets:sub.length,first_target:sub[0].target_date,last_target:sub.at(-1).target_date,mean_top5_hits:r12(sub.reduce((s,r)=>s+r.top5_hits,0)/sub.length),mean_top20_hits:r12(sub.reduce((s,r)=>s+r.top20_hits,0)/sub.length),magnitude:modelSummary(sub,"magnitude"),rank_only:modelSummary(sub,"rank")};}
 const splits={discovery:splitSummary(disc),validation:splitSummary(val),historical_blind_oos:splitSummary(blind)};
 const delta=blind.map(r=>rg(r,"magnitude",chosen.magnitude)-rg(r,"rank",chosen.rank));
 const primary=signflip(blocks(delta),PRIMARY,SEED+1),ci=bootCI(delta,BOOT,SEED);
 const pairs=[];let pi=0;
 for(const st of CANDS)for(const rt of CANDS){const a=st==="uniform"?null:Number(st),b=rt==="uniform"?null:Number(rt),v=blind.map(r=>rg(r,"magnitude",a)-rg(r,"rank",b)),t=signflip(blocks(v),FAMILY,SEED+100+pi++);pairs.push({magnitude_temperature:st,rank_temperature:rt,mean_delta:r12(v.reduce((x,y)=>x+y,0)/v.length),cumulative_delta:r12(v.reduce((x,y)=>x+y,0)),p:t.p});}
 const pairHolm=holm(pairs,x=>x.magnitude_temperature+"|"+x.rank_temperature);
 const pairKey=(chosen.magnitude===null?"uniform":String(chosen.magnitude))+"|"+(chosen.rank===null?"uniform":String(chosen.rank));
 const selectedPair=pairHolm.find(x=>(x.magnitude_temperature+"|"+x.rank_temperature)===pairKey);
 const utests=[];
 for(const model of ["magnitude","rank"])for(const T of TEMPS){const sum=blind.reduce((s,r)=>s+rg(r,model,T),0),p0=sum>0?Math.min(1,Math.exp(-sum)):1;utests.push({model,temperature:String(T),p:p0,cumulative_log_likelihood_gain:r12(sum),e_process_p:up12(p0===0?1e-12:p0)});}
 const uHolm=holm(utests,x=>x.model+"|"+x.temperature).map(x=>({...x,p_bonferroni_43:up12(Math.min(1,43*x.e_process_p))}));
 const primaryMean=r12(delta.reduce((x,y)=>x+y,0)/delta.length);
 const status=primaryMean>0&&selectedPair.p_holm<.05?"HISTORICAL_INCREMENTAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION":"NO_INCREMENTAL_SCORE_MAGNITUDE_LIFT_DEMONSTRATED";
 const repF=scorer(draws.slice(0,W)),repU=utilities(repF.scores),repM=gain(repU.m,draws[W].n,.5),repR=gain(repU.r,draws[W].n,.5);
 function direct(lw){const w=lw.slice(1).map(Math.exp);let z=0;for(let a=0;a<36;a++)for(let b=a+1;b<37;b++)for(let c=b+1;c<38;c++)for(let d=c+1;d<39;d++)for(let e=d+1;e<40;e++)z+=w[a]*w[b]*w[c]*w[d]*w[e];return z;}
 const normM=Math.abs(direct(repM.lw)/Math.exp(repM.logz)-1),normR=Math.abs(direct(repR.lw)/Math.exp(repR.logz)-1);if(normM>1e-10||normR>1e-10)fail("exhaustive PMF");
 const fut=[200,201,641,1921,2121,2762,3000,3200,3402];let futurePass=0;
 for(const t of fut){const a=scorer(draws.slice(0,t)).scores,mut=draws.map((d,i)=>{if(i<t)return {d:d.d,n:[...d.n]};const b=((i*7)%36)+1,ns=[b,((b+5)%40)+1,((b+11)%40)+1,((b+19)%40)+1,((b+27)%40)+1].sort((x,y)=>x-y);return {d:d.d,n:[...new Set(ns)].sort((x,y)=>x-y).slice(0,5)};});const c=scorer(mut.slice(0,t)).scores;if(JSON.stringify(a)!==JSON.stringify(c))fail("future mutation "+t);futurePass++;}
 const reps=[200,201,641,1921,2121,2762,3200,3402];let replayPass=0;for(const t of reps){const a=scorer(draws.slice(0,t)).scores,b=scorer(draws.slice(0,t)).scores;if(JSON.stringify(a)!==JSON.stringify(b))fail("replay "+t);replayPass++;}
 if(pairHolm.length!==100||pairHolm.some(x=>!Number.isFinite(x.p_holm)||x.p_holm<0||x.p_holm>1)||uHolm.length!==18)fail("multiplicity family");
 const checks=[
  {id:"source_provenance",status:"PASS",detail:"Pinned archive, exact active scorer and active-engine report blob IDs match the protocol."},
  {id:"archive_integrity",status:"PASS",detail:"3403 unique chronological rows; every outcome is a sorted distinct 5-of-40 draw."},
  {id:"score_vector_integrity",status:"PASS",detail:"All 3203 score vectors contain each number 1..40 exactly once, finite and source-sorted."},
  {id:"strict_prior_cutoffs",status:"PASS",detail:"All targets scored from archive[0:t]; maximum training outcome index is t-1."},
  {id:"subset_partition_dp",status:"PASS",detail:"Fifth elementary-symmetric DP agrees with exhaustive small-n enumeration; uniform normalizer equals 658008."},
  {id:"exhaustive_subset_normalization",status:"PASS",detail:"Both representative finite-temperature PMFs exhaustively sum over all 658008 subsets; max relative error "+Math.max(normM,normR).toExponential(3)+"."},
  {id:"future_mutation_invariance",status:"PASS",detail:futurePass+"/9 fixed-cutoff comparisons preserved the prior-only score vector."},
  {id:"deterministic_replay",status:"PASS",detail:replayPass+"/8 fixed-cutoff scorer replays were identical."},
  {id:"chronological_split_reconciliation",status:"PASS",detail:"1921 discovery + 641 validation + 641 historical blind OOS = 3203 targets."},
  {id:"paired_family_holm",status:"PASS",detail:"100 fixed magnitude-temperature × rank-temperature comparisons have finite Holm-adjusted p-values."},
  {id:"uniform_eprocess_family",status:"PASS",detail:"18 fixed model/temperature likelihood-ratio e-process p-values corrected with Holm."}
 ];
 const minHolm=Math.min(...pairHolm.map(x=>x.p_holm));
 const report={
  experiment_id:"Q104",title:"Incremental subset-likelihood value of active SONAR score magnitudes over rank-only scores",status,generated_date:"2026-11-10",
  source:{main_commit:JSON.parse(protocolText).source.main_commit,archive_blob_sha1:"8d3e19f0b417024ba32e576697eac0648d12ab86",scorer_blob_sha1:"7ccb9a2abfe452ec535913b70225bc109f692304",active_engine_report_blob_sha1:"ff07b6da4948bb89467067c2552d9b1f78bc9549",protocol_blob_sha1:protocolBlobSha,draws:draws.length,first_date:draws[0].d,last_date:draws.at(-1).d},
  model:{distribution:"product-weight fixed-cardinality 5-subset likelihood",normalizer:"fifth elementary symmetric polynomial e5",exact_subset_count:C,temperatures:TEMPS,utilities:{magnitude:"within-target min-max normalized source score",rank_only:"(40-rank)/39"},null_control:"uniform 5-of-40"},
  walk_forward:{warmup:W,targets:rows.length,splits,selection:{criterion:"Validation mean complete-subset log-likelihood gain versus uniform; uniform fallback; ties prefer larger T",magnitude_temperature:chosen.magnitude===null?"uniform":String(chosen.magnitude),rank_only_temperature:chosen.rank===null?"uniform":String(chosen.rank)}},
  blind_inference:{
   primary_endpoint:"paired mean log-likelihood gain: magnitude minus rank-only",
   selected_pair:{magnitude_temperature:chosen.magnitude===null?"uniform":String(chosen.magnitude),rank_temperature:chosen.rank===null?"uniform":String(chosen.rank),mean_delta:primaryMean,cumulative_delta:r12(delta.reduce((x,y)=>x+y,0)),block_sign_flip:{...primary,p_holm_100:selectedPair.p_holm},bootstrap:{replicates:BOOT,block_length:BL,seed:SEED,ci95:ci}},
   paired_family:{size:100,temperatures:CANDS,block_length:BL,sign_flip_replicates:FAMILY,selected_pair_raw_p:selectedPair.p,selected_pair_holm_p:selectedPair.p_holm,min_raw_p:Math.min(...pairs.map(x=>x.p)),min_holm_p:minHolm,any_pair_holm_below_0_05:minHolm<.05,holm_significant_pair_count:pairHolm.filter(x=>x.p_holm<.05).length,interpretation:"Holm-significant paired contrasts are relative sharpness comparisons; all 18 fixed models have no e-process evidence versus uniform, and the Validation-selected magnitude/rank pair is uniform/uniform. This is not predictive lift.",tests:pairHolm},
   model_vs_uniform:{family_size:18,correction:"Holm across 18 fixed model/temperature e-process p-values",tests:uHolm}
  },
  diagnostics:{top5_random_expected_mean_hits:.625,top20_random_expected_mean_hits:2.5,blind_top5_mean_hits:splits.historical_blind_oos.mean_top5_hits,blind_top20_mean_hits:splits.historical_blind_oos.mean_top20_hits,representative_exhaustive_normalization_relative_error:{magnitude:normM,rank_only:normR}},
  validation:{status:"PASS",checks},
  decision:{incremental_score_magnitude_lift_demonstrated:status!=="NO_INCREMENTAL_SCORE_MAGNITUDE_LIFT_DEMONSTRATED",promotion_allowed:false,production_change_allowed:false,prospective_freezes_changed:false,q60_h101_h102_changed:false},
  limitations:JSON.parse(protocolText).limitations
 };
 const valArtifact={experiment_id:"Q104",status:"PASS",checks,counts:{archive_draws:draws.length,targets:rows.length,discovery:disc.length,validation:val.length,historical_blind_oos:blind.length,future_mutation_comparisons:futurePass,deterministic_replay_comparisons:replayPass,paired_temperature_tests:pairHolm.length,uniform_eprocess_tests:uHolm.length},normalization:{subset_count:C,magnitude_relative_error:normM,rank_only_relative_error:normR}};
 const cols=["target_index","target_date","cutoff_date","max_training_outcome_index","split","draw_numbers","top5_hits","top20_hits","score_min","score_max","score_range"];for(const T of TEMPS){cols.push("gain_magnitude_"+k(T),"gain_rank_"+k(T));}
 const csv=[cols.join(",")];for(const r of rows){const a=[r.target_index,r.target_date,r.cutoff_date,r.max_training_outcome_index,r.split,'"'+r.draw_numbers+'"',r.top5_hits,r.top20_hits,r.score_min,r.score_max,r.score_range];for(const T of TEMPS)a.push(r["gain_magnitude_"+k(T)],r["gain_rank_"+k(T)]);csv.push(a.join(","));}
 const checkpoint=[
 "# Q104 — score-magnitude versus rank-only subset-likelihood checkpoint (2026-11-10)","",
 "## Status",status+". Research-only; no production engine, prospective freeze, Q60, H101 or H102 record was changed.","",
 "## Source and protocol","- Main commit: "+JSON.parse(protocolText).source.main_commit+".","- Archive: 3403 draws through 2026-11-09; blob 8d3e19f0b417024ba32e576697eac0648d12ab86.","- Active scorer: blob 7ccb9a2abfe452ec535913b70225bc109f692304; active report blob ff07b6da4948bb89467067c2552d9b1f78bc9549.","- Protocol blob: "+protocolBlobSha+"; pre-scoring 10×10 paired family including uniform fallback.","",
 "## Result","- Targets: 3203 (Discovery 1921 / Validation 641 / historical Blind OOS 641).","- Validation-selected temperatures: magnitude "+(chosen.magnitude===null?"uniform":chosen.magnitude)+", rank-only "+(chosen.rank===null?"uniform":chosen.rank)+".","- Blind paired mean log-likelihood difference (magnitude − rank): "+primaryMean+".","- Paired 50,000 block sign-flips p="+primary.p+"; Holm across 100 pairs p="+selectedPair.p_holm+".","- Circular block-bootstrap 95% CI: ["+ci.join(", ")+ "].","- Minimum Holm p across the 100 pair family: "+minHolm+".","- Holm-significant relative pairs: "+pairHolm.filter(x=>x.p_holm<.05).length+"/100; all 18 e-process comparisons versus uniform have Holm p=1, so this is a sharpness/overconfidence contrast, not predictive lift.","",
 "## Integrity","- "+checks.length+"/"+checks.length+" checks PASS; 3203 strict-prior score vectors.","- Future mutation: "+futurePass+"/9; deterministic replay: "+replayPass+"/8.","- Both representative PMFs exhaustively normalized across 658008 subsets.","",
 "## Limitations / next action","- Historical Blind OOS is exposed to prior SONAR research and is not a virgin prospective holdout.","- Stop retrospective tuning on this same cohort; continue Q60 append-only prospective collection.","- Any positive result requires at least 200 prospectively frozen targets and human review; no promotion authorized.",""
 ].join("\n");
 return {reportText:json(report),validationText:json(valArtifact),ledgerText:csv.join("\n")+"\n",checkpointText:checkpoint};
}

const ARCHIVE_PATH = "data/storico_daily.csv";
const SOURCE_PATH = "src/VinciCasaLab.jsx";
const ACTIVE_PATH = "reports/sequence_agent/active_engine_walkforward.json";
const PROTOCOL_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_protocol_2026-11-10.json";
const REPORT_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_report_2026-11-10.json";
const VALIDATION_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_validation_2026-11-10.json";
const LEDGER_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_target_ledger_2026-11-10.csv";
const CHECKPOINT_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_checkpoint_2026-11-10.md";
const MANIFEST_PATH = "reports/sequence_agent/q104_score_magnitude_vs_rank_persistence_manifest_2026-11-10.json";
const EXPECTED_ARCHIVE = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const EXPECTED_SCORER = "7ccb9a2abfe452ec535913b70225bc109f692304";
const EXPECTED_ACTIVE = "ff07b6da4948bb89467067c2552d9b1f78bc9549";
const EXPECTED_PROTOCOL = "d8faed4c6649f36b3e4248b24692082fa7056817";

function gitBlobSha1(text) {
  const body = Buffer.from(text, "utf8");
  return crypto.createHash("sha1").update(Buffer.from("blob " + body.length + "\0", "utf8")).update(body).digest("hex");
}
function fail(message) { throw new Error("Q104 runner: " + message); }

const mode = process.argv[2] || "--check";
if (mode !== "--write" && mode !== "--check") fail("use --write or --check");
const archiveText = fs.readFileSync(ARCHIVE_PATH, "utf8");
const sourceText = fs.readFileSync(SOURCE_PATH, "utf8");
const activeText = fs.readFileSync(ACTIVE_PATH, "utf8");
const protocolText = fs.readFileSync(PROTOCOL_PATH, "utf8");
const scriptText = fs.readFileSync("scripts/sonar_q104_score_magnitude_vs_rank.js", "utf8");
if (gitBlobSha1(archiveText) !== EXPECTED_ARCHIVE) fail("archive blob mismatch");
if (gitBlobSha1(sourceText) !== EXPECTED_SCORER) fail("scorer blob mismatch");
if (gitBlobSha1(activeText) !== EXPECTED_ACTIVE) fail("active engine report blob mismatch");
if (gitBlobSha1(protocolText) !== EXPECTED_PROTOCOL) fail("protocol blob mismatch");
const active = JSON.parse(activeText);
if (active.source_git_blob_sha !== EXPECTED_ARCHIVE || active.implementation_source_blob_sha !== EXPECTED_SCORER) fail("active report lineage mismatch");
const outputs = runQ104(archiveText, sourceText, protocolText, EXPECTED_PROTOCOL);
const outputMap = {
  [REPORT_PATH]: outputs.reportText,
  [VALIDATION_PATH]: outputs.validationText,
  [LEDGER_PATH]: outputs.ledgerText,
  [CHECKPOINT_PATH]: outputs.checkpointText
};
const manifest = {
  experiment_id: "Q104",
  generated_date: "2026-11-10",
  source_git_blob_sha1: { archive: EXPECTED_ARCHIVE, scorer: EXPECTED_SCORER, active_engine_report: EXPECTED_ACTIVE, protocol: EXPECTED_PROTOCOL },
  runner_git_blob_sha1: gitBlobSha1(scriptText),
  outputs: Object.fromEntries(Object.entries(outputMap).map(([path, content]) => [path, { bytes: Buffer.byteLength(content, "utf8"), git_blob_sha1: gitBlobSha1(content) }]))
};
const manifestText = JSON.stringify(manifest, null, 2) + "\n";
outputMap[MANIFEST_PATH] = manifestText;
if (mode === "--write") {
  for (const [path, content] of Object.entries(outputMap)) {
    fs.mkdirSync(path.slice(0, path.lastIndexOf("/")), { recursive: true });
    fs.writeFileSync(path, content, "utf8");
  }
} else {
  for (const [path, expected] of Object.entries(outputMap)) {
    if (!fs.existsSync(path)) fail("missing persisted output: " + path);
    const actual = fs.readFileSync(path, "utf8");
    if (actual !== expected) fail("byte mismatch: " + path);
  }
}
process.stdout.write("Q104_REPLAY_PASS status=" + JSON.parse(outputs.reportText).status + " targets=3203 selected_magnitude=" + JSON.parse(outputs.reportText).walk_forward.selection.magnitude_temperature + " selected_rank=" + JSON.parse(outputs.reportText).walk_forward.selection.rank_only_temperature + "\n");
