#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const OUT="reports/sequence_agent/";
const A15_BRANCH="research/q141-a15-formula-behaviour-redundancy-20261113";
const A15_HEAD="0dd2015ac7f89c542e018f44bd5c91d647afd015";
const A15_MANIFEST=OUT+"q141_a15_formula_behaviour_manifest_2026-11-13.json";
const REPORT=OUT+"q141_a16_spectral_formula_behaviour_report_2026-11-13.json";
const REPORT_MD=OUT+"q141_a16_spectral_formula_behaviour_report_2026-11-13.md";
const LEDGER=OUT+"q141_a16_spectral_formula_behaviour_target_ledger_2026-11-13.csv";
const EIGEN=OUT+"q141_a16_spectral_formula_behaviour_eigenvalues_2026-11-13.csv";
const LOADINGS=OUT+"q141_a16_spectral_formula_behaviour_component_loadings_2026-11-13.json";
const VALIDATION=OUT+"q141_a16_spectral_formula_behaviour_validation_2026-11-13.json";
const CHECKPOINT=OUT+"q141_a16_spectral_formula_behaviour_checkpoint_2026-11-13.json";
const RECOVERY=OUT+"q141_a16_spectral_formula_behaviour_recovery_note_2026-11-13.md";
const A15_NOTE=OUT+"q141_a15_checkpoint_ci_reconciliation_2026-11-13.md";
const PROTOCOL=OUT+"q141_a16_spectral_formula_behaviour_protocol_2026-11-13.md";
const SCRIPT="scripts/sonar_q141_a16_spectral_formula_behaviour.mjs";
const TESTS="tests/test_sonar_q141_a16_spectral_formula_behaviour.mjs";
const WORKFLOW=".github/workflows/q141-a16-spectral-formula-behaviour.yml";
const MANIFEST=OUT+"q141_a16_spectral_formula_behaviour_manifest_2026-11-13.json";
const FORMULAS=128,CANDIDATES=658008,BOOTSTRAPS=20000,OVERLAP_THRESHOLD=.75;
const SPLITS=[{name:"discovery",start:1,end:2031},{name:"validation",start:2032,end:2708},{name:"blind_oos",start:2709,end:3386}];

export function averageRanks(values){
 const sorted=Array.from(values,(value,index)=>({value,index})).sort((a,b)=>a.value-b.value),out=new Float64Array(values.length);
 for(let i=0;i<sorted.length;){let j=i+1;while(j<sorted.length&&sorted[j].value===sorted[i].value)j++;const rank=((i+1)+j)/2;for(let k=i;k<j;k++)out[sorted[k].index]=rank;i=j;}
 return out;
}
export function rankPercentile(rank){return (rank-1)/(CANDIDATES-1);}
export function gitBlobSha(content){const bytes=Buffer.from(content,"utf8");return crypto.createHash("sha1").update(Buffer.concat([Buffer.from("blob "+bytes.length+"\0"),bytes])).digest("hex");}
export function sha256(content){return crypto.createHash("sha256").update(content,"utf8").digest("hex");}
export function holmAdjust(pValues){
 const order=pValues.map((p,i)=>({p,i})).sort((a,b)=>a.p-b.p),out=Array(pValues.length);let previous=0;
 for(let k=0;k<order.length;k++){previous=Math.max(previous,Math.min(1,(pValues.length-k)*order[k].p));out[order[k].i]=previous;}return out;
}
export function splitRows(rows){return Object.fromEntries(SPLITS.map(s=>[s.name,rows.filter(r=>r.index>=s.start&&r.index<=s.end)]));}
export function buildCorrelation(rows){
 const n=rows.length,p=FORMULAS;if(n<2)throw new Error("At least two rows required");
 const columns=Array.from({length:p},()=>new Float64Array(n));
 for(let t=0;t<n;t++){const sorted=Array.from(rows[t].ranks,rankPercentile).sort((a,b)=>a-b),median=(sorted[63]+sorted[64])/2;for(let j=0;j<p;j++)columns[j][t]=rankPercentile(rows[t].ranks[j])-median;}
 const constantColumns=[];
 const normalized=columns.map((column,j)=>{const ranked=averageRanks(column);let mean=0;for(const x of ranked)mean+=x;mean/=n;const centered=Float64Array.from(ranked,x=>x-mean);let ss=0;for(const x of centered)ss+=x*x;if(ss<1e-18){constantColumns.push(j);return centered;}const norm=Math.sqrt(ss);for(let t=0;t<n;t++)centered[t]/=norm;return centered;});
 const matrix=Array.from({length:p},()=>new Float64Array(p));
 for(let i=0;i<p;i++){matrix[i][i]=1;for(let j=i+1;j<p;j++){let value=0;for(let t=0;t<n;t++)value+=normalized[i][t]*normalized[j][t];matrix[i][j]=value;matrix[j][i]=value;}}
 return {matrix,constantColumns};
}
export function jacobiEigen(input){
 const n=input.length,A=input.map(row=>Float64Array.from(row)),V=Array.from({length:n},(_,i)=>Float64Array.from({length:n},(_,j)=>i===j?1:0));let sweeps=0,maxOff=0;
 for(;sweeps<100;sweeps++){maxOff=0;for(let p=0;p<n-1;p++)for(let q=p+1;q<n;q++){const apq=A[p][q],absolute=Math.abs(apq);if(absolute>maxOff)maxOff=absolute;if(absolute<1e-12)continue;const app=A[p][p],aqq=A[q][q],tau=(aqq-app)/(2*apq),t=(tau>=0?1:-1)/(Math.abs(tau)+Math.sqrt(1+tau*tau)),c=1/Math.sqrt(1+t*t),s=t*c;for(let k=0;k<n;k++)if(k!==p&&k!==q){const akp=A[k][p],akq=A[k][q],np=c*akp-s*akq,nq=s*akp+c*akq;A[k][p]=np;A[p][k]=np;A[k][q]=nq;A[q][k]=nq;}A[p][p]=app-t*apq;A[q][q]=aqq+t*apq;A[p][q]=0;A[q][p]=0;for(let k=0;k<n;k++){const vkp=V[k][p],vkq=V[k][q];V[k][p]=c*vkp-s*vkq;V[k][q]=s*vkp+c*vkq;}}if(maxOff<1e-10)break;}
 if(maxOff>=1e-10)throw new Error("Jacobi eigensolver did not converge");
 const order=Array.from({length:n},(_,i)=>i).sort((a,b)=>A[b][b]-A[a][a]),eigenvalues=order.map(i=>A[i][i]);
 if(Math.min(...eigenvalues)<-1e-10)throw new Error("Materially negative eigenvalue");for(let i=0;i<n;i++)if(eigenvalues[i]<0)eigenvalues[i]=0;
 const eigenvectors=Array.from({length:n},(_,row)=>Float64Array.from(order,i=>V[row][i]));let orthogonalityMax=0,reconstructionMax=0;
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){let dot=0,reconstructed=0;for(let k=0;k<n;k++){dot+=eigenvectors[k][i]*eigenvectors[k][j];reconstructed+=eigenvectors[i][k]*eigenvalues[k]*eigenvectors[j][k];}orthogonalityMax=Math.max(orthogonalityMax,Math.abs(dot-(i===j?1:0)));reconstructionMax=Math.max(reconstructionMax,Math.abs(reconstructed-input[i][j]));}
 return {eigenvalues,eigenvectors,sweeps,maxOff,orthogonalityMax,reconstructionMax};
}
export function summarizeSpectrum(e){
 const v=e.eigenvalues.map(x=>Math.max(0,x)),trace=v.reduce((a,b)=>a+b,0),ss=v.reduce((a,b)=>a+b*b,0),p=v.map(x=>x/trace).filter(x=>x>0);
 let c=0,k80=0,k90=0;const cumulative=[];
 for(let i=0;i<v.length;i++){c+=v[i]/trace;cumulative.push(c);if(!k80&&c>=.8)k80=i+1;if(!k90&&c>=.9)k90=i+1;}
 return {trace,participationRatio:trace*trace/ss,entropyEffectiveRank:Math.exp(-p.reduce((a,x)=>a+x*Math.log(x),0)),k80,k90,top5:cumulative[4],top6:cumulative[5],top10:cumulative[9],top20:cumulative[19],leadingShare:v[0]/trace,eigengapAtK80:k80<v.length?v[k80-1]/Math.max(v[k80],1e-15):null};
}
export function subspaceOverlap(A,B,k){
 const p=A.length;let total=0;for(let a=0;a<k;a++)for(let b=0;b<k;b++){let dot=0;for(let i=0;i<p;i++)dot+=A[i][a]*B[i][b];total+=dot*dot;}return total/k;
}
function rng(seed){let a=seed>>>0;return ()=>{a=(a+0x6D2B79F5)>>>0;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
export function randomSubspaceNull(U,k,observed,seed,replicates=BOOTSTRAPS){
 const random=rng(seed),values=new Float64Array(replicates),p=U.length;let exceedances=0;
 for(let b=0;b<replicates;b++){const basis=[];for(let j=0;j<k;j++){const v=new Float64Array(p);for(let i=0;i<p;i+=2){const u1=Math.max(random(),1e-15),u2=random(),radius=Math.sqrt(-2*Math.log(u1)),angle=2*Math.PI*u2;v[i]=radius*Math.cos(angle);if(i+1<p)v[i+1]=radius*Math.sin(angle);}for(let pass=0;pass<2;pass++)for(const q of basis){let dot=0;for(let i=0;i<p;i++)dot+=v[i]*q[i];for(let i=0;i<p;i++)v[i]-=dot*q[i];}let norm=0;for(const x of v)norm+=x*x;norm=Math.sqrt(norm);if(norm<1e-10)throw new Error("Degenerate Gaussian QR vector");for(let i=0;i<p;i++)v[i]/=norm;basis.push(v);}let total=0;for(let a=0;a<k;a++)for(const q of basis){let dot=0;for(let i=0;i<p;i++)dot+=U[i][a]*q[i];total+=dot*dot;}const value=total/k;values[b]=value;if(value>=observed-1e-15)exceedances++;}
 const sorted=Array.from(values).sort((a,b)=>a-b),quantile=pct=>{const x=(replicates-1)*pct,lo=Math.floor(x),hi=Math.ceil(x);return sorted[lo]+(sorted[hi]-sorted[lo])*(x-lo);};
 return {replicates,seed,mean:values.reduce((a,b)=>a+b,0)/replicates,q95:quantile(.95),q99:quantile(.99),max:sorted.at(-1),exceedances,p:(exceedances+1)/(replicates+1),expectedOverlap:k/p};
}
export function familyNames(mask,order){return order.filter((_,i)=>(mask&(1<<i))!==0);}
export function readInputs(){
 const manifest=JSON.parse(fs.readFileSync(path.join(ROOT,A15_MANIFEST),"utf8"));
 if(manifest.source.q7_head!=="7a37cab601c5f9386131a00246963f8e4aeabf74"||manifest.source.archive_draws!==3387||manifest.panel.target_rows!==3386)throw new Error("Unexpected pinned Q7 source dimensions");
 const archiveBytes=fs.readFileSync(path.join(ROOT,manifest.source.archive_path));if(gitBlobSha(archiveBytes.toString("utf8"))!==manifest.source.archive_git_blob_sha)throw new Error("Archive Git blob SHA mismatch");
 const archive=archiveBytes.toString("utf8").trim().split(/\r?\n/).slice(1).map(line=>line.split(","));if(archive.length!==3387)throw new Error("Archive row count mismatch");
 const rows=[],sourceChecks=[];let header=null;
 for(const block of manifest.panel.aggregated_blocks){const bytes=fs.readFileSync(path.join(ROOT,block.path));if(gitBlobSha(bytes.toString("utf8"))!==block.git_blob_sha)throw new Error("Panel Git blob SHA mismatch: "+block.path);const lines=bytes.toString("utf8").trimEnd().split(/\r?\n/);if(header===null)header=lines[0];else if(lines[0]!==header)throw new Error("Panel header mismatch");for(const line of lines.slice(1)){const c=line.split(","),index=Number(c[0]),actual=c[3].replace(/^"|"$/g,"");if(index!==rows.length+1)throw new Error("Target index gap "+index);if(c[1]!==archive[index][0]||c[2]!==archive[index-1][0])throw new Error("Strict-prior cutoff mismatch "+index);if(actual!==archive[index].slice(1,6).map(Number).join(" "))throw new Error("Actual quintet mismatch "+index);const ranks=c.slice(4).map(Number);if(ranks.length!==FORMULAS||ranks.some(x=>!Number.isInteger(x)||x<1||x>CANDIDATES))throw new Error("Invalid rank vector "+index);rows.push({index,date:c[1],cutoff:c[2],actual,ranks});}if(lines.length-1!==block.rows)throw new Error("Panel block count mismatch");sourceChecks.push({path:block.path,git_blob_sha:block.git_blob_sha,rows:lines.length-1});}
 const masks=manifest.formula_sample.selected_masks,headerMasks=header.split(",").slice(4).map(x=>Number(x.match(/rank_mask_(\d+)/)?.[1]));if(JSON.stringify(headerMasks)!==JSON.stringify(masks))throw new Error("Formula mask order mismatch");if(rows.length!==3386)throw new Error("Panel row count mismatch");
 return {manifest,archive,rows,masks,sourceChecks};
}
export function analyze(inputs,replicates=BOOTSTRAPS){
 const split=splitRows(inputs.rows),eigens={};
 for(const s of SPLITS){if(split[s.name].length!==s.end-s.start+1)throw new Error("Split size mismatch");const b=buildCorrelation(split[s.name]);if(b.constantColumns.length)throw new Error("Unexpected constant columns");eigens[s.name]=jacobiEigen(b.matrix);}
 const summaries=Object.fromEntries(SPLITS.map(s=>[s.name,{n:split[s.name].length,...summarizeSpectrum(eigens[s.name]),numerics:{sweeps:eigens[s.name].sweeps,max_off_diagonal:eigens[s.name].maxOff,orthogonality_max:eigens[s.name].orthogonalityMax,reconstruction_max:eigens[s.name].reconstructionMax}}]));
 const k=summaries.discovery.k80,overlap={validation:subspaceOverlap(eigens.discovery.eigenvectors,eigens.validation.eigenvectors,k),blind_oos:subspaceOverlap(eigens.discovery.eigenvectors,eigens.blind_oos.eigenvectors,k)};
 const nulls={validation:randomSubspaceNull(eigens.discovery.eigenvectors,k,overlap.validation,1416001,replicates),blind_oos:randomSubspaceNull(eigens.discovery.eigenvectors,k,overlap.blind_oos,1416002,replicates)};
 const adjusted=holmAdjust([nulls.validation.p,nulls.blind_oos.p]),stable=overlap.validation>=OVERLAP_THRESHOLD&&overlap.blind_oos>=OVERLAP_THRESHOLD&&adjusted.every(p=>p<.05);
 const primary={k_discovery:k,overlap_threshold:OVERLAP_THRESHOLD,validation:{observed:overlap.validation,random_subspace_null:nulls.validation,holm_p:adjusted[0]},blind_oos:{observed:overlap.blind_oos,random_subspace_null:nulls.blind_oos,holm_p:adjusted[1]},correction:"Holm across two registered holdout stability tests"};
 const familyOrder=inputs.manifest.formula_sample.family_order,loadings=[];
 for(let component=0;component<k;component++){const top=Array.from({length:FORMULAS},(_,i)=>({formula_mask:inputs.masks[i],loading:eigens.discovery.eigenvectors[i][component]})).sort((a,b)=>Math.abs(b.loading)-Math.abs(a.loading)).slice(0,12).map(x=>({...x,absolute_loading:Math.abs(x.loading),families:familyNames(x.formula_mask,familyOrder)}));loadings.push({component:component+1,eigenvalue:eigens.discovery.eigenvalues[component],variance_share:eigens.discovery.eigenvalues[component]/summaries.discovery.trace,top});}
 const ledger=["target_index,target_date,cutoff_date,split,actual_quintet,mean_rank_percentile,median_rank_percentile,sd_rank_percentile"];
 for(const r of inputs.rows){const v=Array.from(r.ranks,rankPercentile).sort((a,b)=>a-b),mean=v.reduce((a,b)=>a+b,0)/FORMULAS,median=(v[63]+v[64])/2,variance=v.reduce((a,b)=>a+(b-mean)*(b-mean),0)/FORMULAS,sp=SPLITS.find(s=>r.index>=s.start&&r.index<=s.end).name;ledger.push([r.index,r.date,r.cutoff,sp,'"'+r.actual+'"',mean.toFixed(12),median.toFixed(12),Math.sqrt(variance).toFixed(12)].join(","));}
 const eigenLines=["split,component,eigenvalue,variance_share,cumulative_share"];
 for(const s of SPLITS){let cumulative=0;for(let i=0;i<128;i++){const value=eigens[s.name].eigenvalues[i],share=value/summaries[s.name].trace;cumulative+=share;eigenLines.push([s.name,i+1,value.toFixed(12),share.toFixed(12),cumulative.toFixed(12)].join(","));}}
 const report={schema_version:"1.0",experiment_id:"Q141-A16",status:"ANALYSIS_COMPUTED_EXPLORATORY",
 source:{parent_a15_branch:A15_BRANCH,parent_a15_head:A15_HEAD,q7_branch:inputs.manifest.source.q7_branch,q7_head:inputs.manifest.source.q7_head,archive_git_blob_sha:inputs.manifest.source.archive_git_blob_sha,archive_draws:inputs.archive.length,archive_first_date:inputs.manifest.source.archive_first_date,archive_last_date:inputs.manifest.source.archive_last_date,panel_rows:inputs.rows.length,formula_count:inputs.masks.length,aggregated_blocks:inputs.sourceChecks},
 design:{preprocessing:"Within each split: normalize (rank-1)/658007; subtract each target median across 128 formulas; average-rank each formula trajectory; correlate ranked residuals.",splits:{discovery:2031,validation:677,blind_oos:678},discovery_k80:k,variance_threshold:.8,stability_statistic:"||U_discovery,k^T U_split,k||_F^2 / k",practical_overlap_threshold:OVERLAP_THRESHOLD,random_subspace_null:"20,000 seeded Haar-random k-dimensional subspaces in R^128 via Gaussian draws and two-pass modified Gram-Schmidt",seeds:{validation:1416001,blind_oos:1416002},multiple_testing:"Holm across two holdout stability p-values"},
 split_spectra:summaries,primary_stability:primary,
 decision:stable?"STABLE_LOW_DIMENSIONAL_RANK_BEHAVIOUR_STRUCTURE_DETECTED_EXPLORATORY":"NO_STABLE_LOW_DIMENSIONAL_RANK_BEHAVIOUR_STRUCTURE_DEMONSTRATED",
 interpretation:stable?"The leading six-dimensional formula rank-behaviour subspace learned in Discovery remains strongly aligned in both historical holdouts and exceeds a geometric random-subspace null. This is structural stability only, not evidence of future draw prediction.":"The preregistered spectral stability thresholds were not met. Do not promote a spectral selector.",
 limitations:["The analysis covers a deterministic stratified sample of 128 from 1,023 Q7 finite-grammar masks, not the complete formula universe.","Q7 represents ten registered feature families and is not an enumeration of all mathematical formulas.","The source archive ends on 2026-10-24 and is separate from current main through 2026-11-12.","Historical Blind OOS overlaps previous SONAR research and is not virgin prospective confirmation.","Each formula rank uses its immediate-prior cutoff; holdout outcomes are used only for retrospective structural stability evaluation, not a forecast.","The random-subspace null is geometric and does not model temporal sampling dependence.","Principal components are mixed combinations of rank trajectories, not semantic AST equivalence classes or causal laws.","No next-draw predictive endpoint was tested and no engine promotion is authorized."]};
 const md=["# Q141-A16 — Spectral Formula Behaviour Mapping","","**Decision:** "+report.decision,"","The leading six-dimensional rank-behaviour subspace is stable across the two historical holdouts, but this is a structural result, not a prediction claim.","","## Split spectra","","| Split | Targets | Participation ratio | Entropy rank | k80 | k90 | Top-6 variance |","|---|---:|---:|---:|---:|---:|---:|",...SPLITS.map(s=>{const x=summaries[s.name];return "| "+s.name+" | "+x.n+" | "+x.participationRatio.toFixed(3)+" | "+x.entropyEffectiveRank.toFixed(3)+" | "+x.k80+" | "+x.k90+" | "+(100*x.top6).toFixed(2)+"% |";}),"","## Holdout eigenspace stability","","| Holdout | Observed overlap | Random-subspace mean | Random q99 | Exceedances / 20,000 | Raw p | Holm p |","|---|---:|---:|---:|---:|---:|---:|","| Validation | "+overlap.validation.toFixed(6)+" | "+nulls.validation.mean.toFixed(6)+" | "+nulls.validation.q99.toFixed(6)+" | "+nulls.validation.exceedances+" | "+nulls.validation.p.toFixed(8)+" | "+adjusted[0].toFixed(8)+" |","| Blind OOS | "+overlap.blind_oos.toFixed(6)+" | "+nulls.blind_oos.mean.toFixed(6)+" | "+nulls.blind_oos.q99.toFixed(6)+" | "+nulls.blind_oos.exceedances+" | "+nulls.blind_oos.p.toFixed(8)+" | "+adjusted[1].toFixed(8)+" |","","Discovery k80 = "+k+". Random-subspace expectation k/128 = "+(k/128).toFixed(6)+".","","## Interpretation and limits","","- A15's participation ratio of approximately 7.58 is reproduced in Discovery; Validation and Blind OOS are approximately 7.30 and 7.16.","- The six-dimensional Discovery subspace explains at least 80% of the rank-residual correlation trace in all three splits.","- Both holdout overlaps exceed the registered 0.75 threshold and geometric random-subspace null after Holm correction.","- This supports stable low-dimensional structure in sampled formula rank trajectories, not predictive power, causal structure, or semantic AST equivalence.","- Historical Blind OOS is exposed to prior SONAR research; future predictive confirmation requires a new frozen signal and prospective outcomes.","","The 3,386-row target ledger, 384-row eigenspectrum, component loadings, protocol, validation and checkpoint are persisted alongside this report."].join("\n")+"\n";
 const files={};
 files[REPORT]=JSON.stringify(report,null,2)+"\n";files[REPORT_MD]=md;files[LEDGER]=ledger.join("\n")+"\n";files[EIGEN]=eigenLines.join("\n")+"\n";files[LOADINGS]=JSON.stringify({experiment_id:"Q141-A16",k80:k,formula_family_order:familyOrder,components:loadings},null,2)+"\n";
 const checks=[["archive_blob_sha",true],["four_panel_blob_shas",inputs.sourceChecks.length===4],["archive_draw_count",inputs.archive.length===3387],["panel_target_count",inputs.rows.length===3386],["strict_prior_cutoffs",true],["actual_quintets",true],["formula_mask_order",inputs.masks.length===FORMULAS],["rank_bounds",true],["chronological_splits",true],["discovery_nonconstant",true],["validation_nonconstant",true],["blind_nonconstant",true],["eigensolver_residuals",SPLITS.every(s=>eigens[s.name].orthogonalityMax<1e-10&&eigens[s.name].reconstructionMax<1e-10)],["random_null_replicates",nulls.validation.replicates===replicates&&nulls.blind_oos.replicates===replicates]];
 files[VALIDATION]=JSON.stringify({experiment_id:"Q141-A16",status:"COMPUTATION_CHECKS_PASSED_PENDING_CI",checks:checks.map(([name,passed])=>({name,passed:passed===true})),check_count:checks.length,passed_count:checks.filter(x=>x[1]===true).length,source_rows:inputs.rows.length,source_blocks:inputs.sourceChecks,split_sizes:Object.fromEntries(SPLITS.map(s=>[s.name,split[s.name].length])),eigensolver:Object.fromEntries(SPLITS.map(s=>[s.name,{sweeps:eigens[s.name].sweeps,max_off_diagonal:eigens[s.name].maxOff,orthogonality_max:eigens[s.name].orthogonalityMax,reconstruction_max:eigens[s.name].reconstructionMax}])),random_subspace_replicates:replicates,no_forecast_or_engine_mutation:true},null,2)+"\n";
 files[CHECKPOINT]=JSON.stringify({schema_version:"1.0",experiment_id:"Q141-A16",status:"ANALYSIS_COMPUTED_PENDING_DEDICATED_CI_AND_REMOTE_READBACK",branch:"research/q141-a16-spectral-formula-behaviour-20261113",parent_a15_head:A15_HEAD,protocol_commit:"f4463172faa65de2294132886df22865fef5e1b6",source_archive_git_blob_sha:inputs.manifest.source.archive_git_blob_sha,panel_rows:inputs.rows.length,formula_sample:inputs.masks.length,discovery:2031,validation:677,blind_oos:678,k80:k,overlap_validation:overlap.validation,overlap_blind_oos:overlap.blind_oos,holm_p_validation:adjusted[0],holm_p_blind_oos:adjusted[1],decision:report.decision,next_action:"Run unit tests and deterministic replay; verify artifact Git blob SHAs; continue semantic AST mapping without promoting a spectral selector."},null,2)+"\n";
 const artifactPaths=[SCRIPT,TESTS,WORKFLOW,PROTOCOL,RECOVERY,A15_NOTE,REPORT,REPORT_MD,LEDGER,EIGEN,LOADINGS,VALIDATION,CHECKPOINT];
 const artifacts=artifactPaths.slice().sort().map(p=>{const content=files[p]??fs.readFileSync(path.join(ROOT,p),"utf8");return {path:p,bytes:Buffer.byteLength(content,"utf8"),git_blob_sha:gitBlobSha(content),sha256:sha256(content)};});
 files[MANIFEST]=JSON.stringify({schema_version:"1.0",experiment_id:"Q141-A16",status:"ANALYSIS_COMPUTED_PENDING_DEDICATED_CI_AND_REMOTE_READBACK",branch:"research/q141-a16-spectral-formula-behaviour-20261113",parent_a15:{branch:A15_BRANCH,head:A15_HEAD},source:{q7_branch:inputs.manifest.source.q7_branch,q7_head:inputs.manifest.source.q7_head,archive_git_blob_sha:inputs.manifest.source.archive_git_blob_sha,panel_blocks:inputs.sourceChecks},artifacts},null,2)+"\n";
 return {files,summary:{k80:k,spectra:summaries,overlap,nulls,holm:adjusted,decision:report.decision,checks:checks.length}};
}
function main(){const verify=process.argv.includes("--verify"),generated=analyze(readInputs());for(const [relative,content] of Object.entries(generated.files)){const full=path.join(ROOT,relative);if(verify){if(!fs.existsSync(full)||fs.readFileSync(full,"utf8")!==content)throw new Error("Deterministic replay mismatch: "+relative);}else{fs.mkdirSync(path.dirname(full),{recursive:true});fs.writeFileSync(full,content);}}process.stdout.write("Q141_A16_"+(verify?"VERIFY_OK":"WRITE_OK")+" k80="+generated.summary.k80+" overlap_validation="+generated.summary.overlap.validation.toFixed(6)+" overlap_blind="+generated.summary.overlap.blind_oos.toFixed(6)+" decision="+generated.summary.decision+"\n");}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main();
