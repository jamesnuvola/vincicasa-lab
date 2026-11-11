#!/usr/bin/env node
import fs from 'node:fs';
import { createHash } from 'node:crypto';
const D='reports/sequence_agent';
const P={
 protocol:D+'/q125_rank_decile_calibration_protocol_2026-11-11.json',
 source:D+'/q125_source_q123_rank_ledger_2026-11-11.csv',
 runner:'scripts/sonar_q125_rank_decile_calibration.mjs',
 report:D+'/q125_rank_decile_calibration_report_2026-11-11.json',
 ledger:D+'/q125_rank_decile_calibration_target_ledger_2026-11-11.csv',
 validation:D+'/q125_rank_decile_calibration_validation_2026-11-11.json',
 checkpoint:D+'/q125_rank_decile_calibration_checkpoint_2026-11-11.md',
 manifest:D+'/q125_rank_decile_calibration_persistence_manifest_2026-11-11.json'
};
const read=p=>fs.readFileSync(p,'utf8');
const sha=s=>{const b=Buffer.from(s,'utf8');return createHash('sha1').update('blob '+b.length+String.fromCharCode(0)).update(b).digest('hex');};
const protocolText=read(P.protocol),protocol=JSON.parse(protocolText),sourceText=read(P.source);
if(sha(sourceText)!==protocol.source.git_blob_sha)throw new Error('source SHA mismatch');
const lines=sourceText.trimEnd().split(/\r?\n/),h=lines[0].split(','),ix=Object.fromEntries(h.map((x,i)=>[x,i]));
const rows=lines.slice(1).map(line=>{const c=line.split(',');return {idx:+c[ix.target_index],date:c[ix.target_date],cutoff:c[ix.history_cutoff],r:c[ix.draw_ranks].split(';').map(Number),sum:+c[ix.rank_sum],top5:+c[ix.top5_hits],top10:+c[ix.top10_hits],top20:+c[ix.top20_hits]};});
if(rows.length!==3204)throw new Error('row count');
for(let i=0;i<rows.length;i++){const x=rows[i];if(x.idx!==200+i)throw new Error('index');if(Date.parse(x.cutoff)>=Date.parse(x.date))throw new Error('cutoff');if(i&&Date.parse(x.date)<=Date.parse(rows[i-1].date))throw new Error('chronology');if(x.r.length!==5||new Set(x.r).size!==5||x.r.some(v=>!Number.isInteger(v)||v<1||v>40))throw new Error('rank values');if(x.r.reduce((a,b)=>a+b,0)!==x.sum)throw new Error('rank sum');if(x.r.filter(v=>v<=5).length!==x.top5||x.r.filter(v=>v<=10).length!==x.top10||x.r.filter(v=>v<=20).length!==x.top20)throw new Error('top-k reconcile');}
function sum(rs){const c=Array(10).fill(0),vectors=[];let rank=0;for(const x of rs){const v=Array(10).fill(0);for(const r of x.r){c[Math.floor((r-1)/4)]++;v[Math.floor((r-1)/4)]++;rank+=r;}vectors.push(v);}const n=rs.length,e=n*.5,chi=c.reduce((a,b)=>a+(b-e)*(b-e)/e,0),trend=c.reduce((a,b,i)=>a+b*(10-i),0);return {n,c,chi,trend,gain:trend/n-27.5,meanRank:rank/(5*n),vectors};}
const discovery=sum(rows.slice(0,1922)),validation=sum(rows.slice(1922,2563)),blind=sum(rows.slice(2563));
for(const s of [discovery,validation,blind])if(s.c.reduce((a,b)=>a+b,0)!==5*s.n)throw new Error('hit conservation');
function rng(a){return function(){let t=a+=0x6D2B79F5;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296;};}
const R=20000,rand=rng(0x12520261111>>>0),e=blind.n*.5;let ex1=0,ex2=0;
for(let q=0;q<R;q++){const c=Array(10).fill(0);for(let t=0;t<blind.n;t++){const seen=new Set();while(seen.size<5){const z=Math.floor(rand()*40);if(!seen.has(z)){seen.add(z);c[Math.floor(z/4)]++;}}}let chi=0,tr=0;for(let i=0;i<10;i++){chi+=(c[i]-e)*(c[i]-e)/e;tr+=c[i]*(10-i);}if(chi>=blind.chi-1e-12)ex1++;if(tr>=blind.trend-1e-12)ex2++;}
const p1=(ex1+1)/(R+1),p2=(ex2+1)/(R+1),ps=[p1,p2].sort((a,b)=>a-b),h1=Math.min(1,2*ps[0]),h2=Math.min(1,Math.max(h1,ps[1])),holm1=p1<=p2?h1:h2,holm2=p2<p1?h1:h2;
const B=10000,L=20,br=rng(0x125B007),boot=[],bd=Array.from({length:10},()=>[]),nblocks=Math.ceil(blind.n/L);
for(let q=0;q<B;q++){const c=Array(10).fill(0);let used=0;for(let b=0;b<nblocks&&used<blind.n;b++){const start=Math.floor(br()*blind.n),take=Math.min(L,blind.n-used);for(let j=0;j<take;j++){const v=blind.vectors[(start+j)%blind.n];for(let k=0;k<10;k++)c[k]+=v[k];}used+=take;}let tr=0;for(let k=0;k<10;k++){tr+=c[k]*(10-k);bd[k].push(c[k]/blind.n);}boot.push(tr/blind.n-27.5);}
function qtl(a,p){const x=[...a].sort((u,v)=>u-v),z=(x.length-1)*p,l=Math.floor(z),u=Math.ceil(z);return x[l]+(x[u]-x[l])*(z-l);}
const trendCI=[qtl(boot,.025),qtl(boot,.975)],decCI=bd.map(a=>[qtl(a,.025),qtl(a,.975)]);
const report=JSON.parse(read(P.report)),validationFile=JSON.parse(read(P.validation)),ledgerText=read(P.ledger);
const close=(a,b)=>Math.abs(a-b)<1e-10;
if(report.source.ledger_blob_sha!==sha(sourceText))throw new Error('report source pin');
if(report.splits.discovery.decile_hit_counts.join(',')!==discovery.c.join(','))throw new Error('discovery counts');
if(report.splits.validation.decile_hit_counts.join(',')!==validation.c.join(','))throw new Error('validation counts');
if(report.splits.blind_oos.decile_hit_counts.join(',')!==blind.c.join(','))throw new Error('blind counts');
if(!close(report.blind_inference.omnibus.p_value,p1)||!close(report.blind_inference.top_heavy_trend.p_value,p2))throw new Error('p-value replay');
if(!close(report.blind_inference.omnibus.p_holm,holm1)||!close(report.blind_inference.top_heavy_trend.p_holm,holm2))throw new Error('Holm replay');
if(!close(report.blind_inference.top_heavy_trend.bootstrap_ci95[0],trendCI[0])||!close(report.blind_inference.top_heavy_trend.bootstrap_ci95[1],trendCI[1]))throw new Error('bootstrap replay');
if(validationFile.passed_checks!==18||validationFile.total_checks!==18||validationFile.status!=='PASS')throw new Error('validation status');
if(ledgerText.trimEnd().split(/\r?\n/).length!==3204+1)throw new Error('ledger rows');
const ledgerRows=ledgerText.trimEnd().split(/\r?\n/);
const ledgerHeader=['target_index','target_date','history_cutoff','split','draw_ranks','rank_sum','mean_rank','top5_hits','top10_hits','top20_hits',...Array.from({length:10},(_,i)=>'d'+(i+1))].join(',');
if(ledgerRows[0]!==ledgerHeader)throw new Error('ledger header');
for(let i=0;i<rows.length;i++){
  const x=rows[i],d=Array(10).fill(0);
  for(const r of x.r)d[Math.floor((r-1)/4)]++;
  const split=i<1922?'discovery':i<2563?'validation':'blind_oos';
  const expected=[x.idx,x.date,x.cutoff,split,x.r.join(';'),x.sum,(x.sum/5).toFixed(12),x.top5,x.top10,x.top20,...d].join(',');
  if(ledgerRows[i+1]!==expected)throw new Error('ledger content mismatch at '+i);
}
const manifest=JSON.parse(read(P.manifest));
for(const a of manifest.artifacts){const b=fs.readFileSync(a.path);const content=b.toString('utf8');if(sha(content)!==a.sha||b.length!==a.bytes)throw new Error('manifest mismatch '+a.path);}
console.log('Q125 CHECK PASS: 3204 targets; decile counts and 20,000 conditional-randomization / 10,000 block-bootstrap statistics reproduced; 18/18 validation; manifest verified.');
