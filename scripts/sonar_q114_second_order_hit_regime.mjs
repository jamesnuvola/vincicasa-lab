#!/usr/bin/env node
import fs from 'node:fs';
import crypto from 'node:crypto';
const alpha=200, blockLength=20;
const root='reports/sequence_agent/';
const srcLedgerPath=root+'q114_source_q113_active_engine_hit_regime_target_ledger_2026-11-11.csv';
const srcFreezePath=root+'q114_source_q113_active_engine_hit_regime_prospective_freeze_2026-11-11.json';
function parseCSV(s){const out=[];let row=[],field='',quoted=false;for(let i=0;i<s.length;i++){const c=s[i];if(quoted){if(c==='"'&&s[i+1]==='"'){field+='"';i++;}else if(c==='"')quoted=false;else field+=c;}else{if(c==='"')quoted=true;else if(c===','){row.push(field);field='';}else if(c==='\n'){row.push(field);out.push(row);row=[];field='';}else if(c!=='\r')field+=c;}}if(field.length||row.length){row.push(field);out.push(row);}const h=out.shift();return out.filter(r=>r.length===h.length).map(r=>Object.fromEntries(h.map((k,i)=>[k,r[i]])));}
const rows=parseCSV(fs.readFileSync(srcLedgerPath,'utf8')).map(r=>({date:r.target_date,cutoff:r.history_cutoff,prev:Number(r.previous_top20_hits),y:Number(r.actual_top20_hits)}));
const q113=JSON.parse(fs.readFileSync(srcFreezePath,'utf8'));
const choose=(n,k)=>{if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
const q0=Array.from({length:6},(_,k)=>choose(20,k)*choose(20,5-k)/choose(40,5));
const makeCounts=()=>({c1:Array.from({length:6},()=>Array(6).fill(0)),n1:Array(6).fill(0),c2:Array.from({length:6},()=>Array.from({length:6},()=>Array(6).fill(0))),n2:Array.from({length:6},()=>Array(6).fill(0))});
const add1=(c,a,y)=>{c.c1[a][y]++;c.n1[a]++;};
const add2=(c,a,b,y)=>{c.c2[a][b][y]++;c.n2[a][b]++;};
const p1=(c,a)=>q0.map((q,k)=>(alpha*q+c.c1[a][k])/(alpha+c.n1[a]));
const p2=(c,a,b)=>{const p=p1(c,a);return q0.map((q,k)=>(alpha*p[k]+c.c2[a][b][k])/(alpha+c.n2[a][b]));};
const br=(p,y)=>p.reduce((s,x,k)=>s+(x-(k===y?1:0))**2,0);
function compute(rs){const c=makeCounts(),out=[];for(let i=0;i<rs.length;i++){const r=rs[i];if(i===0){add1(c,r.prev,r.y);continue;}const a=r.prev,b=rs[i-1].prev,y=r.y,P1=p1(c,a),P2=p2(c,a,b);out.push({i,date:r.date,cutoff:r.cutoff,a,b,y,split:i<=1920?'discovery':i<=2561?'validation':'blind_oos',support:c.n2[a][b],b0:br(q0,y),b1:br(P1,y),b2:br(P2,y),l0:-Math.log(q0[y]),l1:-Math.log(P1[y]),l2:-Math.log(P2[y])});add1(c,a,y);add2(c,a,b,y);}return {out,c};}
const m=compute(rows),r=m.out;
const mean=(a,f)=>a.reduce((s,x)=>s+f(x),0)/a.length;
const seg={discovery:r.filter(x=>x.split==='discovery'),validation:r.filter(x=>x.split==='validation'),blind_oos:r.filter(x=>x.split==='blind_oos')};
const expected=(a,k)=>a.reduce((s,p,i)=>s+i*p,0);
function forecastAt(rs,i){const c=makeCounts();for(let j=0;j<i;j++){add1(c,rs[j].prev,rs[j].y);if(j>=1)add2(c,rs[j].prev,rs[j-1].prev,rs[j].y);}return {p1:p1(c,rs[i].prev),p2:p2(c,rs[i].prev,rs[i-1].prev)};}
const idx=[50,400,800,1200,1600,2000,2400,2800,3202];let mutation=0;for(const i of idx){const a=forecastAt(rows,i),changed=rows.map((x,j)=>j>i?{...x,prev:(x.prev+3)%6,y:(x.y+2)%6}:x),b=forecastAt(changed,i);if(JSON.stringify(a)===JSON.stringify(b))mutation++;}
const replay=JSON.stringify(r)===JSON.stringify(compute(rows).out);
const report=JSON.parse(fs.readFileSync(root+'q114_second_order_hit_regime_report_2026-11-11.json','utf8'));
const validation=JSON.parse(fs.readFileSync(root+'q114_second_order_hit_regime_validation_2026-11-11.json','utf8'));
const freeze=JSON.parse(fs.readFileSync(root+'q114_second_order_hit_regime_prospective_freeze_2026-11-11.json','utf8'));
const ledger=fs.readFileSync(root+'q114_second_order_hit_regime_target_ledger_2026-11-11.csv','utf8');
const ledgerRows=parseCSV(ledger).length;
const p1next=p1(m.c,freeze.previous_hits_lag1),p2next=p2(m.c,freeze.previous_hits_lag1,freeze.previous_hits_lag2);
const diff=Math.max(...p1next.map((x,k)=>Math.abs(x-q113.transition_pmf[k])));
const close=(a,b,t=1e-10)=>Math.abs(a-b)<=t;
const checks=[
 Math.abs(q0.reduce((a,b)=>a+b,0)-1)<1e-12,
 rows.length===3203,
 rows.every((x,i)=>i===0||x.date>rows[i-1].date),
 rows.every(x=>Number.isInteger(x.prev)&&x.prev>=0&&x.prev<=5&&Number.isInteger(x.y)&&x.y>=0&&x.y<=5),
 rows.slice(1).every((x,i)=>x.prev===rows[i].y),
 r.length===3202,
 seg.discovery.length===1920&&seg.validation.length===641&&seg.blind_oos.length===641,
 mutation===9,
 replay,
 ledgerRows===3202,
 close(diff,0,1e-12),
 close(expected(p1next),freeze.expected_hits_first_order),
 close(expected(p2next),freeze.expected_hits_second_order),
 JSON.stringify(freeze.active_engine_top20)===JSON.stringify(q113.active_engine_top20),
 validation.passed===true&&validation.checks_passed===17,
 close(mean(seg.blind_oos,x=>x.b1-x.b2),report.walk_forward.metrics.blind_oos.m2_vs_m1.brier_gain),
 close(mean(seg.blind_oos,x=>x.l1-x.l2),report.walk_forward.metrics.blind_oos.m2_vs_m1.log_loss_gain),
];
if(checks.some(x=>!x))throw new Error('Q114 replay checks failed: '+checks.map((x,i)=>x?null:i).filter(x=>x!==null).join(','));
const manifest=JSON.parse(fs.readFileSync(root+'q114_second_order_hit_regime_persistence_manifest_2026-11-11.json','utf8'));
for(const [path,meta] of Object.entries(manifest.artifacts)){const bytes=fs.readFileSync(path);const header=Buffer.from('blob '+bytes.length+'\0');const sha=crypto.createHash('sha1').update(Buffer.concat([header,bytes])).digest('hex');if(sha!==meta.git_blob_sha1||bytes.length!==meta.byte_length)throw new Error('Manifest mismatch: '+path);}
console.log(JSON.stringify({experiment_id:'Q114',checks_passed:checks.length,checks_total:checks.length,future_mutation:mutation+'/9',replay:replay?'PASS':'FAIL',m2_vs_m1_blind_brier:mean(seg.blind_oos,x=>x.b1-x.b2),m2_vs_m1_blind_log:mean(seg.blind_oos,x=>x.l1-x.l2),m1_freeze_reconciliation_max_abs_diff:diff,manifest_artifacts:Object.keys(manifest.artifacts).length}));
