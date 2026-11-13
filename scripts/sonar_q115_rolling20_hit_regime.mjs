#!/usr/bin/env node
import fs from "node:fs";
import crypto from "node:crypto";
const R="reports/sequence_agent/";
const SRC=R+"q115_source_q113_active_engine_hit_regime_target_ledger_2026-11-11.csv";
const SF=R+"q115_source_q113_active_engine_hit_regime_prospective_freeze_2026-11-11.json";
const OUT=R+"q115_rolling20_hit_regime_target_ledger_2026-11-11.csv";
const REPORT=R+"q115_rolling20_hit_regime_report_2026-11-11.json";
const VALID=R+"q115_rolling20_hit_regime_validation_2026-11-11.json";
const FREEZE=R+"q115_rolling20_hit_regime_prospective_freeze_2026-11-11.json";
const MANIFEST=R+"q115_rolling20_hit_regime_persistence_manifest_2026-11-11.json";
const W=20,A=200,B=20,SIM=50000,BOOT=10000;
function parseCSV(s){const a=[];let row=[],field="",q=false;for(let i=0;i<s.length;i++){const c=s[i];if(q){if(c==='"'&&s[i+1]==='"'){field+='"';i++;}else if(c==='"')q=false;else field+=c;}else if(c==='"')q=true;else if(c===","){row.push(field);field="";}else if(c==="\n"){row.push(field);a.push(row);row=[];field="";}else if(c!=="\r")field+=c;}if(field.length||row.length){row.push(field);a.push(row);}const h=a.shift();if(!h||a.some(x=>x.length!==h.length))throw Error("CSV width mismatch");return a.map(x=>Object.fromEntries(h.map((k,i)=>[k,x[i]])));}
const choose=(n,k)=>{if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
const q0=Array.from({length:6},(_,k)=>choose(20,k)*choose(20,5-k)/choose(40,5));
const rows=parseCSV(fs.readFileSync(SRC,"utf8")).map((r,i)=>({date:r.target_date,cutoff:r.history_cutoff,prev:+r.previous_top20_hits,y:+r.actual_top20_hits,i}));
if(rows.length!==3203||rows.slice(1).some((r,i)=>r.prev!==rows[i].y)||rows.some(r=>r.cutoff>=r.date))throw Error("source integrity failure");
const prefix=[0];for(const r of rows)prefix.push(prefix.at(-1)+r.y);
const states=rows.map((r,i)=>{if(i<W)return null;const s=prefix[i]-prefix[i-W];return s<=45?0:s<=54?1:2;});
const fresh=()=>({c1:Array.from({length:6},()=>Array(6).fill(0)),n1:Array(6).fill(0),c20:Array.from({length:3},()=>Array(6).fill(0)),n20:Array(3).fill(0)});
const add=(c,r,i)=>{c.c1[r.prev][r.y]++;c.n1[r.prev]++;if(i>=W){c.c20[states[i]][r.y]++;c.n20[states[i]]++;}};
const p1=(c,a)=>q0.map((q,k)=>(A*q+c.c1[a][k])/(A+c.n1[a]));
const p20=(c,s)=>q0.map((q,k)=>(A*q+c.c20[s][k])/(A+c.n20[s]));
const br=(p,y)=>p.reduce((z,v,k)=>z+(v-(k===y?1:0))**2,0),ll=(p,y)=>-Math.log(p[y]);
const mean=(a,f)=>a.reduce((z,x)=>z+f(x),0)/a.length;
const split=i=>i<=1920?"discovery":i<=2561?"validation":"blind_oos";
function run(){const c=fresh(),out=[];for(let i=0;i<rows.length;i++){const r=rows[i];if(i>=W){const a=p1(c,r.prev),b=p20(c,states[i]);out.push({i,date:r.date,cutoff:r.cutoff,prev:r.prev,sum:prefix[i]-prefix[i-W],state:states[i],support:c.n20[states[i]],y:r.y,split:split(i),p1:a,p20:b,b0:br(q0,r.y),b1:br(a,r.y),b20:br(b,r.y),l0:ll(q0,r.y),l1:ll(a,r.y),l20:ll(b,r.y)});}add(c,r,i);}return{out,c};}
function rng(seed){let x=seed>>>0;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;};}
function infer(d,seed){const blocks=[];for(let i=0;i<d.length;i+=B)blocks.push(d.slice(i,i+B).reduce((a,b)=>a+b,0));const gain=mean(d,x=>x),r1=rng(seed);let ge=0;for(let s=0;s<SIM;s++){let z=0;for(const v of blocks)z+=(r1()<.5?-v:v);if(z/d.length>=gain-1e-15)ge++;}const r2=rng(seed+1000),bs=[];for(let s=0;s<BOOT;s++){let z=0,n=0;while(n<d.length){const st=Math.floor(r2()*d.length);for(let j=0;j<B&&n<d.length;j++,n++)z+=d[(st+j)%d.length];}bs.push(z/d.length);}bs.sort((a,b)=>a-b);return{gain,p_value:(ge+1)/(SIM+1),ci95:[bs[124],bs[9874]]};}
function blobSha(path){const b=fs.readFileSync(path);return{byte_length:b.length,git_blob_sha1:crypto.createHash("sha1").update(Buffer.concat([Buffer.from("blob "+b.length+"\0"),b])).digest("hex")};}
const first=run(),second=run(),out=first.out;
const segments={discovery:out.filter(x=>x.split==="discovery"),validation:out.filter(x=>x.split==="validation"),blind_oos:out.filter(x=>x.split==="blind_oos")};
if(segments.discovery.length!==1901||segments.validation.length!==641||segments.blind_oos.length!==641)throw Error("split sizes mismatch");
const metrics={};for(const[k,a]of Object.entries(segments)){metrics[k]={targets:a.length,mean_actual_hits:mean(a,x=>x.y),mean_predicted_hits:{m0:2.5,m1:mean(a,x=>x.p1.reduce((z,v,j)=>z+j*v,0)),m20:mean(a,x=>x.p20.reduce((z,v,j)=>z+j*v,0))},brier:{m0:mean(a,x=>x.b0),m1:mean(a,x=>x.b1),m20:mean(a,x=>x.b20)},log_loss:{m0:mean(a,x=>x.l0),m1:mean(a,x=>x.l1),m20:mean(a,x=>x.l20)},gains:{m20_vs_m0:{brier:mean(a,x=>x.b0-x.b20),log_loss:mean(a,x=>x.l0-x.l20)},m20_vs_m1:{brier:mean(a,x=>x.b1-x.b20),log_loss:mean(a,x=>x.l1-x.l20)},m1_vs_m0:{brier:mean(a,x=>x.b0-x.b1),log_loss:mean(a,x=>x.l0-x.l1)}}};}
const blind=segments.blind_oos;
const tests=[["m20_vs_m0_brier",blind.map(x=>x.b0-x.b20),1152001],["m20_vs_m0_log_loss",blind.map(x=>x.l0-x.l20),1152002],["m20_vs_m1_brier",blind.map(x=>x.b1-x.b20),1152003],["m20_vs_m1_log_loss",blind.map(x=>x.l1-x.l20),1152004]].map(([key,d,seed])=>({key,...infer(d,seed)}));
const ordered=tests.map((x,i)=>({i,p:x.p_value})).sort((a,b)=>a.p-b.p);let adj=0;ordered.forEach((x,i)=>{adj=Math.max(adj,Math.min(1,(4-i)*x.p));tests[x.i].holm_adjusted=adj;});
const header=["target_date","history_cutoff","source_index","previous_top20_hits","rolling20_hit_sum","rolling_state","state_support_before","actual_top20_hits","split","m1_pmf","m20_pmf","baseline_brier","m1_brier","m20_brier","m20_brier_gain_vs_m0","m20_brier_gain_vs_m1","baseline_log_loss","m1_log_loss","m20_log_loss","m20_log_gain_vs_m0","m20_log_gain_vs_m1"];
const esc=v=>/[",\r\n]/.test(String(v))?'"'+String(v).replace(/"/g,'""')+'"':String(v),fmt=v=>v.toFixed(10),names=["LOW","MID","HIGH"];
const ledger=[header.join(",")];for(const x of out)ledger.push([x.date,x.cutoff,x.i,x.prev,x.sum,names[x.state],x.support,x.y,x.split,x.p1.map(fmt).join(" "),x.p20.map(fmt).join(" "),fmt(x.b0),fmt(x.b1),fmt(x.b20),fmt(x.b0-x.b20),fmt(x.b1-x.b20),fmt(x.l0),fmt(x.l1),fmt(x.l20),fmt(x.l0-x.l20),fmt(x.l1-x.l20)].map(esc).join(","));
const ledgerText=ledger.join("\n")+"\n";
const persistedLedger=fs.readFileSync(OUT,"utf8");
if(ledgerText!==persistedLedger){
  const a=ledgerText.split("\n"),b=persistedLedger.split("\n");let i=0;
  while(i<Math.min(a.length,b.length)&&a[i]===b[i])i++;
  console.error(JSON.stringify({first_mismatch_line:i+1,expected:a[i]?.slice(0,420),persisted:b[i]?.slice(0,420),expected_lines:a.length,persisted_lines:b.length}));
  throw Error("ledger replay differs");
}
const report=JSON.parse(fs.readFileSync(REPORT,"utf8"));
for(const k of ["discovery","validation","blind_oos"])for(const m of ["m20_vs_m0","m20_vs_m1"])for(const e of ["brier","log_loss"]){const v=metrics[k].gains[m][e],saved=report.walk_forward.metrics[k].gains[m][e];if(Math.abs(v-saved)>1e-10)throw Error("metric mismatch "+k+" "+m+" "+e);}
for(let i=0;i<4;i++){if(Math.abs(tests[i].gain-report.blind_inference[i].gain)>1e-10||Math.abs(tests[i].p_value-report.blind_inference[i].p_value)>1e-10||Math.abs(tests[i].holm_adjusted-report.blind_inference[i].holm_adjusted)>1e-10)throw Error("inference mismatch "+tests[i].key);}
const sf=JSON.parse(fs.readFileSync(SF,"utf8")),freeze=JSON.parse(fs.readFileSync(FREEZE,"utf8"));
const last20=rows.slice(-W).reduce((z,x)=>z+x.y,0),state=last20<=45?0:last20<=54?1:2,prev=rows.at(-1).y;
const expectedFreeze={sum:last20,state:["LOW","MID","HIGH"][state],support:first.c.n20[state],top20:sf.active_engine_top20};
if(freeze.trailing_20_hit_sum!==expectedFreeze.sum||freeze.rolling_state!==expectedFreeze.state||freeze.rolling_state_support!==expectedFreeze.support||JSON.stringify(freeze.active_engine_top20)!==JSON.stringify(expectedFreeze.top20))throw Error("freeze mismatch");
const p1now=p1(first.c,prev);if(Math.max(...p1now.map((v,k)=>Math.abs(v-sf.transition_pmf[k])))>1e-12)throw Error("Q113 lag1 freeze mismatch");
function forecastAt(data,i){const pref=[0];for(const r of data)pref.push(pref.at(-1)+r.y);const st=data.map((r,j)=>{if(j<W)return null;const s=pref[j]-pref[j-W];return s<=45?0:s<=54?1:2;});const c=fresh();for(let j=0;j<i;j++){c.c1[data[j].prev][data[j].y]++;c.n1[data[j].prev]++;if(j>=W){c.c20[st[j]][data[j].y]++;c.n20[st[j]]++;}}return{p1:p1(c,data[i].prev),p20:p20(c,st[i])};}
let mutation=0;for(const i of [100,500,1000,1500,2000,2400,2800,3000,3182]){const a=forecastAt(rows,i),changed=rows.map((r,j)=>j>i?{...r,prev:(r.prev+3)%6,y:(r.y+2)%6}:r),b=forecastAt(changed,i);if(JSON.stringify(a)===JSON.stringify(b))mutation++;}
if(mutation!==9||JSON.stringify(first.out)!==JSON.stringify(second.out))throw Error("future mutation/replay failure");
const validation=JSON.parse(fs.readFileSync(VALID,"utf8"));if(validation.passed!==true||validation.checks_passed!==19||validation.checks_total!==19)throw Error("validation artifact incomplete");
const manifest=JSON.parse(fs.readFileSync(MANIFEST,"utf8"));
for(const[path,meta]of Object.entries(manifest.artifacts)){const actual=blobSha(path);if(actual.git_blob_sha1!==meta.git_blob_sha1||actual.byte_length!==meta.byte_length)throw Error("manifest mismatch: "+path);}
console.log(JSON.stringify({experiment_id:"Q115",targets:out.length,split_sizes:{discovery:segments.discovery.length,validation:segments.validation.length,blind_oos:segments.blind_oos.length},future_mutation:"9/9",deterministic_replay:"PASS",ledger_replay:"BYTE_IDENTICAL",holm_family:4,manifest_artifacts:Object.keys(manifest.artifacts).length,freeze_state:expectedFreeze.state,freeze_sum:expectedFreeze.sum}));
