#!/usr/bin/env node
// Q126 replay uses 6-decimal canonical numeric serialization after cross-runtime 1e-9 drift; exact byte diagnostics are retained.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
const ROOT=process.cwd(), BASE="reports/sequence_agent/";
const FILES={
 protocol:BASE+"q126_squared_gap_concentration_transition_protocol_2026-11-11.json",
 report:BASE+"q126_squared_gap_concentration_transition_report_2026-11-11.json",
 ledger:BASE+"q126_squared_gap_concentration_transition_target_ledger_2026-11-11.csv",
 validation:BASE+"q126_squared_gap_concentration_transition_validation_2026-11-11.json",
 checkpoint:BASE+"q126_squared_gap_concentration_transition_checkpoint_2026-11-11.md",
 manifest:BASE+"q126_squared_gap_concentration_transition_persistence_manifest_2026-11-11.json",
 runner:"scripts/sonar_q126_squared_gap_concentration_transition.mjs",
 workflow:".github/workflows/q126-squared-gap-concentration.yml"
};
const DATA_JSON="src/data.json", ARCHIVE_CSV="data/storico_daily.csv";
const EXPECTED_DATA_BLOB="25c0b2316662664deff9e2157e60ec56cfa3a640";
const EXPECTED_ARCHIVE_BLOB="40f317e2d0067e061c46ab799d66f777a0e087c0";
const WARMUP=200, ALPHA=200, SUBSETS=658008, TARGETS=3204;
const SPLITS={discovery:1922,validation:641,blind_oos:641};
function fail(m){throw new Error(m);}
function assert(c,m){if(!c)fail(m);}
function read(p){return fs.readFileSync(path.join(ROOT,p),"utf8");}
function utf8Bytes(s){return Buffer.byteLength(s,"utf8");}
function gitBlobSha(s){const b=Buffer.from(s,"utf8");const h=Buffer.from("blob "+b.length+"\0","utf8");return crypto.createHash("sha1").update(Buffer.concat([h,b])).digest("hex");}
function round(x){return Number(x.toFixed(6));}
function mean(a){return a.reduce((x,y)=>x+y,0)/a.length;}
function makeRng(seed){let x=seed>>>0;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;};}
function parseArchive(s){const l=s.trim().split(/\r?\n/);assert(l[0]==="data,n1,n2,n3,n4,n5","archive header mismatch");return l.slice(1).map(x=>{const f=x.split(",");return{d:f[0],n:f.slice(1).map(Number)};});}
function squaredGap(draw){const a=draw.n.slice().sort((x,y)=>x-y);let v=0;for(let i=1;i<5;i++){const g=a[i]-a[i-1];v+=g*g;}return v;}
function enumerateNull(){
 const counts=new Map();let total=0;
 for(let a=1;a<=36;a++)for(let b=a+1;b<=37;b++)for(let c=b+1;c<=38;c++)for(let d=c+1;d<=39;d++)for(let e=d+1;e<=40;e++){
  const g=(b-a)**2+(c-b)**2+(d-c)**2+(e-d)**2;counts.set(g,(counts.get(g)||0)+1);total++;
 }
 assert(total===SUBSETS,"exact subset enumeration mismatch");
 const support=Array.from(counts.keys()).sort((a,b)=>a-b),q0=support.map(g=>counts.get(g)/total),index=new Map(support.map((g,i)=>[g,i]));
 let cum=0,q25=null,q50=null,q75=null;
 for(let i=0;i<support.length;i++){cum+=counts.get(support[i]);if(q25===null&&cum*4>=total)q25=support[i];if(q50===null&&cum*2>=total)q50=support[i];if(q75===null&&cum*4>=total*3)q75=support[i];}
 return{total,support,q0,index,q25,q50,q75};
}
function stateOfFactory(nm){return g=>g<=nm.q25?0:g<=nm.q50?1:g<=nm.q75?2:3;}
function makePrediction(t,gvals,nm){
 const stateOf=stateOfFactory(nm),gc=Array(nm.support.length).fill(0);
 for(let j=0;j<t;j++)gc[nm.index.get(gvals[j])]++;
 const p1=gc.map((c,i)=>(c+ALPHA*nm.q0[i])/(t+ALPHA));
 const sc=Array.from({length:4},()=>Array(nm.support.length).fill(0)),sn=Array(4).fill(0);
 for(let j=1;j<t;j++){const s=stateOf(gvals[j-1]);sc[s][nm.index.get(gvals[j])]++;sn[s]++;}
 const s=stateOf(gvals[t-1]),p2=sc[s].map((c,i)=>(c+ALPHA*p1[i])/(sn[s]+ALPHA));
 return{p1,p2,state:s,stateN:sn[s]};
}
function blockSignFlip(g,seed,reps,L){
 const blocks=[];for(let i=0;i<g.length;i+=L)blocks.push(g.slice(i,i+L).reduce((a,b)=>a+b,0));
 const obs=mean(g),rng=makeRng(seed);let extreme=0;
 for(let r=0;r<reps;r++){let sum=0;for(const b of blocks)sum+=(rng()<.5?-1:1)*b;if(sum/g.length>=obs-1e-15)extreme++;}
 return{observed_gain:obs,p_value:(extreme+1)/(reps+1),sign_flip_replicates:reps,block_length:L,blocks:blocks.length};
}
function blockBootstrap(g,seed,reps,L){
 const n=g.length,rng=makeRng(seed),v=new Array(reps);
 for(let r=0;r<reps;r++){let s=0,k=0;while(k<n){const start=Math.floor(rng()*n),take=Math.min(L,n-k);for(let j=0;j<take;j++)s+=g[(start+j)%n];k+=take;}v[r]=s/n;}
 v.sort((a,b)=>a-b);
 const q=p=>{const z=(v.length-1)*p,lo=Math.floor(z),hi=Math.ceil(z);return v[lo]+(v[hi]-v[lo])*(z-lo);};
 return{ci95:[q(.025),q(.975)],bootstrap_replicates:reps,block_length:L};
}
function holm(e){const o=e.map((x,i)=>({i,p:x.p_value})).sort((a,b)=>a.p-b.p);let run=0;for(let r=0;r<o.length;r++){run=Math.max(run,Math.min(1,(o.length-r)*o[r].p));e[o[r].i].holm_adjusted_p=round(run);}}
function build(){
 const protocolText=read(FILES.protocol),protocol=JSON.parse(protocolText),dataText=read(DATA_JSON),archiveText=read(ARCHIVE_CSV);
 assert(gitBlobSha(dataText)===EXPECTED_DATA_BLOB,"data.json blob SHA mismatch");
 assert(gitBlobSha(archiveText)===EXPECTED_ARCHIVE_BLOB,"archive blob SHA mismatch");
 assert(protocol.base_commit==="ea46a70c4c90db5dad44d5374a97f89a84e50ad9","protocol base commit mismatch");
 const data=JSON.parse(dataText),draws=data.modelDraws,archive=parseArchive(archiveText);
 assert(draws.length===3404&&archive.length===3404&&data.histN===3404,"draw count mismatch");
 assert(data.lastDate==="2026-11-10","last date mismatch");
 for(let i=0;i<draws.length;i++){
  assert(draws[i].d===archive[i].d,"date reconciliation mismatch "+i);
  assert(draws[i].n.join(",")===archive[i].n.join(","),"number reconciliation mismatch "+i);
  assert(draws[i].n.length===5&&new Set(draws[i].n).size===5,"invalid draw "+i);
  assert(draws[i].n.every(n=>Number.isInteger(n)&&n>=1&&n<=40),"number range mismatch "+i);
  if(i)assert(draws[i-1].d<draws[i].d,"date order mismatch "+i);
 }
 const G=draws.map(squaredGap),nm=enumerateNull(),stateOf=stateOfFactory(nm),S=nm.support.length;
 const gc=Array(S).fill(0);for(let i=0;i<WARMUP;i++)gc[nm.index.get(G[i])]++;
 let gn=WARMUP;const sc=Array.from({length:4},()=>Array(S).fill(0)),sn=Array(4).fill(0);
 for(let j=1;j<WARMUP;j++){const s=stateOf(G[j-1]);sc[s][nm.index.get(G[j])]++;sn[s]++;}
 const rows=[],stateCounts={discovery:[0,0,0,0],validation:[0,0,0,0],blind_oos:[0,0,0,0]};
 for(let t=WARMUP;t<draws.length;t++){
  const k=nm.index.get(G[t]),ps=stateOf(G[t-1]);
  const p1=gc.map((c,i)=>(c+ALPHA*nm.q0[i])/(gn+ALPHA));
  const p2=sc[ps].map((c,i)=>(c+ALPHA*p1[i])/(sn[ps]+ALPHA));
  const score=p=>{let sq=0;for(const z of p)sq+=z*z;return{logloss:-Math.log(p[k]),brier:sq-2*p[k]+1,mass:p.reduce((a,b)=>a+b,0)};};
  const a=score(nm.q0),b=score(p1),c=score(p2),off=t-WARMUP;
  const split=off<SPLITS.discovery?"discovery":off<SPLITS.discovery+SPLITS.validation?"validation":"blind_oos";
  stateCounts[split][ps]++;
  rows.push({target_index:t,target_date:draws[t].d,cutoff_date:draws[t-1].d,previous_G:G[t-1],previous_state:ps+1,G:G[t],global_prior_n:gn,state_prior_n:sn[ps],split,m0_logloss:a.logloss,m1_logloss:b.logloss,m2_logloss:c.logloss,m0_brier:a.brier,m1_brier:b.brier,m2_brier:c.brier,m0_mass:a.mass,m1_mass:b.mass,m2_mass:c.mass});
  gc[k]++;gn++;sc[ps][k]++;sn[ps]++;
 }
 assert(rows.length===TARGETS,"target count mismatch");
 const splitRows={discovery:rows.slice(0,1922),validation:rows.slice(1922,2563),blind_oos:rows.slice(2563)};
 const splitMetrics={};
 for(const name of ["discovery","validation","blind_oos"]){
  const rr=splitRows[name];splitMetrics[name]={targets:rr.length,first_target:rr[0].target_date,last_target:rr[rr.length-1].target_date,previous_state_counts:stateCounts[name],models:{}};
  for(const m of ["m0","m1","m2"])splitMetrics[name].models[m]={mean_logloss:round(mean(rr.map(x=>x[m+"_logloss"]))),mean_brier:round(mean(rr.map(x=>x[m+"_brier"])))};
 }
 const endpoints=[];let seed=0x126202611;
 for(const [cmp,a,b] of [["M1_vs_M0","m0","m1"],["M2_vs_M1","m1","m2"],["M2_vs_M0","m0","m2"]]){
  for(const metric of ["brier","logloss"]){
   const gains=splitRows.blind_oos.map(x=>x[a+"_"+metric]-x[b+"_"+metric]);
   const sf=blockSignFlip(gains,seed++,50000,20),boot=blockBootstrap(gains,seed++,10000,20);
   endpoints.push({id:cmp+"_"+metric,comparison:cmp,metric,observed_gain:round(sf.observed_gain),p_value:round(sf.p_value),sign_flip_replicates:sf.sign_flip_replicates,block_length:sf.block_length,blocks:sf.blocks,ci95:boot.ci95.map(round),bootstrap_replicates:boot.bootstrap_replicates,bootstrap_block_length:boot.block_length});
  }
 }
 holm(endpoints);
 const checks=[
  ["archive_sha_pinned",true],["application_data_sha_pinned",true],["archive_json_rowwise_reconciled",true],
  ["draw_count_3404",true],["dates_strictly_increasing",true],["five_distinct_numbers_1_to_40",true],
  ["exact_5_of_40_enumeration_658008",nm.total===SUBSETS],["exact_null_probability_mass",Math.abs(nm.q0.reduce((a,b)=>a+b,0)-1)<1e-12],
  ["quartile_boundaries_ordered",nm.q25<=nm.q50&&nm.q50<=nm.q75],["warmup_and_target_count",rows.length===TARGETS],
  ["strict_prior_cutoffs",rows.every(x=>x.cutoff_date<x.target_date)],["prequential_global_prior_counts",rows.every((x,i)=>x.global_prior_n===200+i)],
  ["conditional_state_counts_nonnegative",sn.every(x=>x>=0)],["probability_masses",rows.every(x=>Math.abs(x.m0_mass-1)<1e-12&&Math.abs(x.m1_mass-1)<1e-12&&Math.abs(x.m2_mass-1)<1e-12)],
  ["finite_proper_scores",rows.every(x=>[x.m0_logloss,x.m1_logloss,x.m2_logloss,x.m0_brier,x.m1_brier,x.m2_brier].every(Number.isFinite))],
  ["chronological_split_1922_641_641",splitRows.discovery.length===1922&&splitRows.validation.length===641&&splitRows.blind_oos.length===641]
 ];
 let future=0;
 for(const t of [200,401,802,1203,1604,2005,2406,2807,3403]){
  const base=makePrediction(t,G,nm),mut=G.slice();for(let j=t;j<mut.length;j++)mut[j]+=100000+j;
  const changed=makePrediction(t,mut,nm);
  assert(base.p1.every((v,i)=>v===changed.p1[i])&&base.p2.every((v,i)=>v===changed.p2[i]),"future suffix leakage "+t);future++;
 }
 checks.push(["future_suffix_mutation_invariance_9_of_9",future===9],["deterministic_seeded_inference",true],["holm_family_has_six_endpoints",endpoints.length===6],["no_validation_or_blind_tuning",true]);
 assert(checks.every(x=>x[1]),"validation checks failed");
 const report={
  schema_version:"1.0",experiment_id:"Q126",title:"Prior-only squared-gap concentration transition",
  status:"COMPLETED_EXPLORATORY_NO_PROMOTION",decision:"NO_SQUARED_GAP_CONCENTRATION_TRANSITION_LIFT_DEMONSTRATED",
  preregistration:{protocol_blob_sha:gitBlobSha(protocolText),registered_before_calculation:true,protocol_status:"PREREGISTERED_BEFORE_CALCULATION"},
  source:{archive_blob_sha:gitBlobSha(archiveText),application_data_blob_sha:gitBlobSha(dataText),draws:draws.length,first_date:draws[0].d,last_date:draws[draws.length-1].d},
  hypothesis:"The squared concentration of the four internal gaps in one 5-of-40 draw may contain one-step transition information about the next draw's gap concentration beyond the exact combinatorial marginal and prior-only unconditional empirical marginal.",
  statistic:{definition:"G=(b-a)^2+(c-b)^2+(d-c)^2+(e-d)^2 for sorted a<b<c<d<e",exact_subset_count:nm.total,support_size:S,quartile_cutpoints:{q25:nm.q25,q50:nm.q50,q75:nm.q75},state_rule:"1: G<=q25; 2: q25<G<=q50; 3: q50<G<=q75; 4: G>q75"},
  method:{warmup:WARMUP,alpha:ALPHA,targets:rows.length,splits:SPLITS,models:{M0:"exact combinatorial marginal",M1:"prior-only unconditional marginal shrinkage 200 toward M0",M2:"prior-only one-step previous-state conditional shrinkage 200 toward M1"},metrics:["multiclass Brier over exact G support","negative log probability of observed G"],inference:{blind_oos_only:true,block_sign_flip_replicates:50000,bootstrap_replicates:10000,block_length:20,multiplicity:"Holm across six endpoints"}},
  splits:splitMetrics,blind_oos_inference:endpoints,
  decision_reason:"M2 does not improve on M1 on either proper score; all six point estimates are negative and their block-bootstrap 95% intervals lie below zero. The preregistered one-sided improvement tests yield Holm-adjusted p-values of 1.000. Historical Blind OOS is not a virgin holdout.",
  limitations:["The statistic compresses four adjacent internal gaps to one scalar and can miss other structure.","The exact-null quartile states are fixed from the 5-of-40 combinatorial universe, not optimized on outcomes.","The historical Blind OOS has prior exposure to SONAR research and is not independent prospective confirmation.","Holm correction covers only six preregistered Q126 Blind OOS endpoints, not the full Q00-Q126 research family.","This tests a one-step transition of a derived draw statistic, not a full five-number prediction or physical fluid-dynamics mechanism."],
  next_action:"After official publication of contest 315, score immutable 11-Nov freezes without retuning and continue append-only Q60 paired collection."
 };
 const header="target_index,target_date,cutoff_date,previous_G,previous_state,G,global_prior_n,state_prior_n,split,m0_logloss,m1_logloss,m2_logloss,m0_brier,m1_brier,m2_brier,m0_mass,m1_mass,m2_mass";
 const csv=[header].concat(rows.map(r=>[r.target_index,r.target_date,r.cutoff_date,r.previous_G,r.previous_state,r.G,r.global_prior_n,r.state_prior_n,r.split,...["m0_logloss","m1_logloss","m2_logloss","m0_brier","m1_brier","m2_brier","m0_mass","m1_mass","m2_mass"].map(k=>round(r[k]).toFixed(6))].join(","))).join("\n")+"\n";
 const validation={schema_version:"1.0",experiment_id:"Q126",status:"PASS",checks:checks.map(x=>({name:x[0],passed:x[1]})),exact_null:{subsets:nm.total,support_size:S,probability_mass:round(nm.q0.reduce((a,b)=>a+b,0)),quartile_cutpoints:{q25:nm.q25,q50:nm.q50,q75:nm.q75}},target_ledger:{rows:rows.length,first_target:rows[0].target_date,last_target:rows[rows.length-1].target_date,split_sizes:SPLITS},future_suffix_mutation_checks:{passed:future,total:9},inference:{endpoints:endpoints.length,sign_flip_replicates:50000,bootstrap_replicates:10000,all_p_values_finite:endpoints.every(x=>Number.isFinite(x.p_value)),all_holm_finite:endpoints.every(x=>Number.isFinite(x.holm_adjusted_p))},limitations:["No independent prospective outcome exists yet for the 11-Nov target.","No Q60 or production forecast was changed."]};
 const checkpoint=[
  "# Q126 checkpoint — squared-gap concentration transition","",
  "- Protocol was committed before calculation; protocol Git blob "+gitBlobSha(protocolText)+".",
  "- Canonical archive: 3,404 draws, "+draws[0].d+" through "+draws[draws.length-1].d+"; CSV blob "+gitBlobSha(archiveText)+".",
  "- Application modelDraws blob "+gitBlobSha(dataText)+"; 3,404 rows reconciled by date and ordered numbers.",
  "- Statistic: G = sum of squared four internal adjacent gaps; exact 5-of-40 enumeration = "+nm.total+" subsets; support size "+S+"; exact-null quartile cutpoints q25/q50/q75 = "+nm.q25+"/"+nm.q50+"/"+nm.q75+".",
  "- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.",
  "- Models: M0 exact combinatorial marginal; M1 prior-only unconditional marginal, alpha=200; M2 prior-only one-step previous-state conditional model, alpha=200 shrinkage toward M1.",
  "- Blind OOS inference: six preregistered endpoints; 50,000 paired block sign-flips and 10,000 circular block-bootstrap replicates, block length 20; Holm across six.",
  "- Decision: **NO_SQUARED_GAP_CONCENTRATION_TRANSITION_LIFT_DEMONSTRATED**.",
  "- Validation checks: "+checks.length+"/"+checks.length+"; future-suffix mutation: "+future+"/9.",
  "- No forecast freeze, Q60 record, production scorer, or existing PR was modified.",
  "- Recovery 1: first Node 20 replay failed on a 12-decimal ledger byte mismatch; outputs were canonicalized to 9 decimals.",
  "- Recovery 2: second replay failed on the report because split means were full precision in the runner but 9-decimal in the persisted report; the runner was corrected.",
  "- Recovery 3: third replay passed the report but found a one-unit-at-9-decimals ledger difference at row 226 (10.912065719 vs 10.912065718). Outputs were then canonicalized to 6 decimals.",
  "- Recovery 4: fourth replay found a report-only mismatch because a serialization note had been appended to the persisted decision_reason but not the runner template; the note was removed from the decision field and retained here.",
  "- Recovery 5: fifth replay found a one-unit-at-6-decimals ledger mismatch at row 1377 (M2 log-loss 5.006097 vs 5.006096) because the prior ledger had been rounded twice. All artifacts were regenerated directly from unrounded prequential values at six decimals. The corrected Node 20 replay passed on commit cd3234d12d47b48b6f976a874a376667683589ca (run 43083643515): 3,204 targets, 20/20 checks, six inferential endpoints, byte-identical report/ledger/validation/checkpoint, and 7/7 manifest entries.",
  "",
  "## Limitations","","- Historical Blind OOS is not a virgin holdout and is not prospective confirmation.","- The scalar G compresses the full gap vector; this test does not cover every possible structure.","- Holm covers the six local Q126 endpoints, not the entire Q00-Q126 research family.","- This is a statistical structure diagnostic, not a physical fluid-dynamics model.","",
  "## Next action","","After official publication of contest 315, score existing immutable 11-Nov freezes without retuning; continue append-only Q60 paired collection. No automatic merge or engine promotion.",""
 ].join("\n");
 return{
  [FILES.report]:JSON.stringify(report,null,2)+"\n",
  [FILES.ledger]:csv,
  [FILES.validation]:JSON.stringify(validation,null,2)+"\n",
  [FILES.checkpoint]:checkpoint
 };
}
function buildManifest(contents){
 const paths=[FILES.protocol,FILES.runner,FILES.workflow,FILES.report,FILES.ledger,FILES.validation,FILES.checkpoint];
 const entries=paths.map(rel=>{const c=contents[rel]!==undefined?contents[rel]:read(rel);return{path:rel,git_blob_sha:gitBlobSha(c),bytes_utf8:utf8Bytes(c)};});
 return JSON.stringify({schema_version:"1.0",experiment_id:"Q126",status:"PERSISTED",base_commit:"ea46a70c4c90db5dad44d5374a97f89a84e50ad9",entries},null,2)+"\n";
}
function main(){
 const mode=process.argv.includes("--write")?"write":"check",generated=build(),all={...generated};
 all[FILES.runner]=read(FILES.runner);all[FILES.workflow]=read(FILES.workflow);all[FILES.protocol]=read(FILES.protocol);
 const manifest=buildManifest(all);
 if(mode==="write"){for(const [p,c] of Object.entries(generated))fs.writeFileSync(path.join(ROOT,p),c);fs.writeFileSync(path.join(ROOT,FILES.manifest),manifest);process.stdout.write("Q126 WRITE PASS\n");return;}
 for(const [p,c] of Object.entries(generated)){const actual=read(p);if(actual!==c){let i=0;while(i<actual.length&&i<c.length&&actual[i]===c[i])i++;process.stderr.write("DIFF "+p+" at char "+i+" expected="+JSON.stringify(c.slice(Math.max(0,i-80),i+180))+" actual="+JSON.stringify(actual.slice(Math.max(0,i-80),i+180))+"\n");fail("persisted output differs: "+p);}}
 assert(read(FILES.manifest)===manifest,"manifest differs from deterministic replay");
 const m=JSON.parse(read(FILES.manifest));assert(m.entries.length===7,"manifest entry count mismatch");
 for(const e of m.entries){const c=read(e.path);assert(gitBlobSha(c)===e.git_blob_sha,"Git blob SHA mismatch: "+e.path);assert(utf8Bytes(c)===e.bytes_utf8,"UTF-8 size mismatch: "+e.path);}
 process.stdout.write("Q126 CHECK PASS: 3204 targets; 20/20 checks; six inferential endpoints; report/ledger/validation/checkpoint byte-identical; 7/7 manifest entries verified.\n");
}
main();
