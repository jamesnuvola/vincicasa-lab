#!/usr/bin/env node
import fs from "node:fs";
import assert from "node:assert/strict";
import crypto from "node:crypto";
const W=200,A=200,BLOCK=20,SIGN=50000,BOOT=10000,SEED=13120261112,D=1922,V=641;
const round=x=>Number(x.toFixed(12)),fmt=x=>x.toFixed(12),mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const choose=(n,k)=>{if(k<0||k>n)return 0;let v=1;for(let i=1;i<=Math.min(k,n-k);i++)v=v*(n-i+1)/i;return v;};
const p0=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/choose(40,5));
function load(){const ls=fs.readFileSync("data/storico_daily.csv","utf8").trim().split(/\r?\n/);assert.equal(ls[0],"data,n1,n2,n3,n4,n5");return ls.slice(1).map(l=>{const p=l.split(",");return{date:p[0],draw:p.slice(1,6).map(Number)};});}
function overlaps(data){const o=Array(data.length).fill(null);for(let i=1;i<data.length;i++){const s=new Set(data[i-1].draw);o[i]=data[i].draw.reduce((z,n)=>z+(s.has(n)?1:0),0);}return o;}
function score(p,y){let b=0;for(let k=0;k<6;k++){const z=p[k]-(k===y?1:0);b+=z*z;}return{brier:b,logloss:-Math.log(p[y])};}
function forecast(data){const o=overlaps(data),m=Array(6).fill(0),t=Array.from({length:6},()=>Array(6).fill(0)),tn=Array(6).fill(0);for(let j=1;j<W;j++)m[o[j]]++;for(let j=2;j<W;j++){t[o[j-1]][o[j]]++;tn[o[j-1]]++;}const out=[];for(let i=W;i<data.length;i++){const prev=o[i-1],y=o[i],mn=m.reduce((s,x)=>s+x,0),rn=tn[prev],p1=p0.map((p,k)=>(m[k]+A*p)/(mn+A)),p2=p1.map((p,k)=>(t[prev][k]+A*p1[k])/(rn+A)),s0=score(p0,y),s1=score(p1,y),s2=score(p2,y);out.push({date:data[i].date,cutoff:data[i-1].date,index:i,prev,y,mn,rn,p0:p0.slice(),p1,p2,s0,s1,s2});m[y]++;t[prev][y]++;tn[prev]++;}return out;}
function ledgerCsv(a){const h=["target_date","history_cutoff","history_draws","previous_overlap","observed_overlap","m1_history_n","m2_transition_n_for_prev"];for(const m of ["p0","p1","p2"])for(let k=0;k<6;k++)h.push(m+"_"+k);h.push("m0_brier","m1_brier","m2_brier","m0_logloss","m1_logloss","m2_logloss");const ls=[h.join(",")];for(const r of a){const v=[r.date,r.cutoff,r.index,r.prev,r.y,r.mn,r.rn];for(const m of ["p0","p1","p2"])for(let k=0;k<6;k++)v.push(fmt(r[m][k]));v.push(fmt(r.s0.brier),fmt(r.s1.brier),fmt(r.s2.brier),fmt(r.s0.logloss),fmt(r.s1.logloss),fmt(r.s2.logloss));ls.push(v.join(","));}return ls.join("\n")+"\n";}
function segment(a){const c=Array(6).fill(0);for(const r of a)c[r.y]++;return{targets:a.length,observed_mean_overlap:round(mean(a.map(x=>x.y))),observed_counts:c,models:{M0:{brier:round(mean(a.map(x=>x.s0.brier))),logloss:round(mean(a.map(x=>x.s0.logloss)))},M1:{brier:round(mean(a.map(x=>x.s1.brier))),logloss:round(mean(a.map(x=>x.s1.logloss)))},M2:{brier:round(mean(a.map(x=>x.s2.brier))),logloss:round(mean(a.map(x=>x.s2.logloss)))}}};}
function rng(seed){let s=seed>>>0;return()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return(s>>>0)/4294967296;};}
function blocks(a){const z=[];for(let i=0;i<a.length;i+=BLOCK)z.push(a.slice(i,i+BLOCK).reduce((s,x)=>s+x,0));return z;}
function infer(name,d,r){const bs=blocks(d),obs=d.reduce((s,x)=>s+x,0);let ge=0;for(let i=0;i<SIGN;i++){let z=0;for(const x of bs)z+=(r()<.5?-x:x);if(z>=obs-1e-12)ge++;}const boot=[];for(let i=0;i<BOOT;i++){let z=0,c=0;while(c<d.length){const st=Math.floor(r()*d.length);for(let k=0;k<BLOCK&&c<d.length;k++,c++)z+=d[(st+k)%d.length];}boot.push(z/d.length);}boot.sort((a,b)=>a-b);return{name,gain:round(mean(d)),p_raw:round((ge+1)/(SIGN+1)),ci95:[round(boot[Math.floor(.025*BOOT)]),round(boot[Math.floor(.975*BOOT)])],blocks:bs.length};}
const data=load(),l=forecast(data),splits={discovery:l.slice(0,D),validation:l.slice(D,D+V),blind_oos:l.slice(D+V)},r=rng(SEED),b=splits.blind_oos;
const inf=[infer("M1_vs_M0_brier",b.map(x=>x.s0.brier-x.s1.brier),r),infer("M1_vs_M0_logloss",b.map(x=>x.s0.logloss-x.s1.logloss),r),infer("M2_vs_M1_brier",b.map(x=>x.s1.brier-x.s2.brier),r),infer("M2_vs_M1_logloss",b.map(x=>x.s1.logloss-x.s2.logloss),r)];
const ord=inf.slice().sort((a,b)=>a.p_raw-b.p_raw);let hp=0;for(let i=0;i<ord.length;i++){hp=Math.max(hp,Math.min(1,(ord.length-i)*ord[i].p_raw));ord[i].p_holm=round(hp);}for(const x of inf)x.p_holm=ord.find(y=>y.name===x.name).p_holm;
const report=JSON.parse(fs.readFileSync("reports/sequence_agent/q131_overlap_count_lag1_report_2026-11-12.json","utf8"));
assert.equal(data.length,3404);assert.equal(l.length,3204);
assert.equal(ledgerCsv(l),fs.readFileSync("reports/sequence_agent/q131_overlap_count_lag1_target_ledger_2026-11-12.csv","utf8"));
assert.deepStrictEqual(segment(splits.discovery),report.chronological_segments.discovery);
assert.deepStrictEqual(segment(splits.validation),report.chronological_segments.validation);
assert.deepStrictEqual(segment(splits.blind_oos),report.chronological_segments.blind_oos);
assert.deepStrictEqual(inf,report.blind_oos_inference);
const val=JSON.parse(fs.readFileSync("reports/sequence_agent/q131_overlap_count_lag1_validation_2026-11-12.json","utf8"));
assert.equal(val.status,"PASS");assert.equal(val.passed_count,21);
const manifest=JSON.parse(fs.readFileSync("reports/sequence_agent/q131_overlap_count_lag1_persistence_manifest_2026-11-12.json","utf8"));
for(const e of manifest.entries){const buf=fs.readFileSync(e.path);const sha=crypto.createHash("sha1").update(Buffer.concat([Buffer.from("blob "+buf.length+"\0"),buf])).digest("hex");assert.equal(buf.length,e.utf8_bytes,e.path+" byte count");assert.equal(sha,e.blob_sha,e.path+" Git blob SHA");}
console.log("Q131 REPLAY PASS: 3,204 targets; 1,922/641/641 split; four inference endpoints reproduced; ledger byte-identical; 21/21 checks; manifest "+manifest.entries.length+"/"+manifest.entries.length+".");
