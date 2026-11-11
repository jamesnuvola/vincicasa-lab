#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const P="reports/sequence_agent/";
const read=p=>fs.readFileSync(path.join(ROOT,p),"utf8");
const sha=s=>{const b=Buffer.from(s,"utf8");return crypto.createHash("sha1").update("blob "+b.length+"\0").update(b).digest("hex");};
const choose=(n,k)=>{if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-i+1)/i;return v;};
const fail=m=>{console.error("Q113 BLOCKED: "+m);process.exit(1);};
const csv=read("data/storico_daily.csv"),app=read("src/VinciCasaLab.jsx"),data=JSON.parse(read("src/data.json"));
const engine=JSON.parse(read(P+"active_engine_walkforward.json")),freeze=JSON.parse(read(P+"q113_active_engine_hit_regime_prospective_freeze_2026-11-11.json"));
const draws=csv.trimEnd().split(/\r?\n/).slice(1).map(line=>{const f=line.split(",");return{d:f[0],n:f.slice(1).map(Number)};});
if(draws.length!==3404||data.modelDraws.length!==draws.length)fail("archive/app size");
for(let i=0;i<draws.length;i++)if(data.modelDraws[i].d!==draws[i].d||data.modelDraws[i].n.join(",")!==draws[i].n.join(","))fail("app mismatch "+i);
function ex(name,next){const a=app.indexOf("function "+name+"("),b=next?app.indexOf("\nfunction "+next+"(",a+1):app.indexOf("\nconst Card =",a+1);if(a<0||b<0)fail("extract "+name);return app.slice(a,b).trim();}
const score=new Function("draws",[ex("overlapCount","sonarTransitionProfile"),ex("sonarTransitionProfile","sonarAnalogCore"),ex("sonarAnalogCore",null),"return sonarAnalogCore(draws);"].join("\n"));
const h=Array(draws.length).fill(null);
for(let t=200;t<draws.length;t++){const r=score(draws.slice(0,t)).scores.map(x=>x.n);const a=new Set(draws[t].n);h[t]=r.slice(0,20).filter(x=>a.has(x)).length;}
const q=Array.from({length:6},(_,k)=>choose(20,k)*choose(20,5-k)/choose(40,5));
const C=Array.from({length:6},()=>Array(6).fill(0)),N=Array(6).fill(0),rows=[];
for(let t=201;t<draws.length;t++){const j=h[t-1],y=h[t],p=q.map((v,k)=>(200*v+C[j][k])/(200+N[j]));rows.push({j,y,p});C[j][y]++;N[j]++;}
if(JSON.stringify(score(draws).scores.map(x=>x.n).slice(0,20))!==JSON.stringify(engine.current_frozen_forecast.top20_ranked))fail("active freeze mismatch");
if(freeze.previous_top20_hits!==h.at(-1)||freeze.history_cutoff!==draws.at(-1).d||freeze.outcome!==null)fail("Q113 freeze mismatch");
const err=Math.max(Math.abs(q.reduce((a,b)=>a+b,0)-1),...rows.map(r=>Math.abs(r.p.reduce((a,b)=>a+b,0)-1)));
if(err>1e-12)fail("PMF normalization");
if(read(P+"q113_active_engine_hit_regime_target_ledger_2026-11-11.csv").trimEnd().split(/\r?\n/).length!==3204)fail("ledger rows");
const report=JSON.parse(read(P+"q113_active_engine_hit_regime_report_2026-11-11.json"));
if(report.walk_forward.targets!==3203||report.decision!=="NO_INCREMENTAL_HIT_REGIME_LIFT_DEMONSTRATED")fail("report");
const validation=JSON.parse(read(P+"q113_active_engine_hit_regime_validation_2026-11-11.json"));
if(!validation.passed||validation.checks_passed!==17)fail("validation");
const manifest=JSON.parse(read(P+"q113_active_engine_hit_regime_persistence_manifest_2026-11-11.json"));
for(const [file,m] of Object.entries(manifest.artifacts)){const s=read(file);if(sha(s)!==m.git_blob_sha1||Buffer.byteLength(s)!==m.byte_length)fail("manifest "+file);}
console.log(JSON.stringify({status:"PASS",targets:rows.length,draws:draws.length,checks:validation.checks_passed,manifest_artifacts:Object.keys(manifest.artifacts).length}));
