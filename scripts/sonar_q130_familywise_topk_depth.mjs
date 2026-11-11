import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

const P='reports/sequence_agent/';
const read=(p)=>fs.readFileSync(p,'utf8');
const fail=(m)=>{throw new Error(m);};
const assert=(ok,m)=>{if(!ok)fail(m);};
const round=(x,n=8)=>Number(x.toFixed(n));
const nums=(s)=>s.trim().split(/\s+/).map(Number);
const sourcePath=P+'historical_rule_ledger.csv';
const protocol=JSON.parse(read(P+'q130_familywise_topk_depth_protocol_2026-11-12.json'));
const sourceBlob=execFileSync('git',['rev-parse','HEAD:'+sourcePath],{encoding:'utf8'}).trim();
assert(sourceBlob===protocol.source.git_blob_sha,'source Git blob SHA differs from preregistration');
try{execFileSync('git',['diff','--quiet','HEAD','--',sourcePath],{stdio:'ignore'});}catch{fail('source working tree differs from committed blob');}

const lines=read(sourcePath).trimEnd().split(/\r?\n/);
const h=lines[0].split(',');
const ix={date:h.indexOf('target_date'),cut:h.indexOf('history_cutoff'),id:h.indexOf('config_id'),top20:h.indexOf('top20'),top10:h.indexOf('top10'),top5:h.indexOf('top5'),hit20:h.indexOf('hit_count'),hit10:h.indexOf('top10_hit_count'),hit5:h.indexOf('top5_hit_count'),actual:h.indexOf('actual_numbers'),mode:h.indexOf('evaluation_mode')};
assert(Object.values(ix).every(x=>x>=0),'missing source column');
const groups=[];let g=null,errors=0;
for(let i=1;i<lines.length;i++){
  const f=lines[i].split(',');
  if(!g||g.date!==f[ix.date]){
    if(g)groups.push(g);
    g={date:f[ix.date],cut:f[ix.cut],actualText:f[ix.actual],actual:nums(f[ix.actual]),cfg:[],ids:new Set()};
  }
  const a5=nums(f[ix.top5]),a10=nums(f[ix.top10]),a20=nums(f[ix.top20]);
  if(g.cut>=g.date||g.actualText!==f[ix.actual]||g.ids.has(f[ix.id])||
     a5.length!==5||a10.length!==10||a20.length!==20||
     new Set(a5).size!==5||new Set(a10).size!==10||new Set(a20).size!==20||
     a5.some((n,j)=>a10[j]!==n)||a10.some((n,j)=>a20[j]!==n)||
     f[ix.mode]!==protocol.source.evaluation_mode)errors++;
  const rank=new Uint8Array(41);rank.fill(255);
  a20.forEach((n,j)=>{if(n<1||n>40||rank[n]!==255)errors++;rank[n]=j+1;});
  const hits=[0,0,0];
  for(const n of g.actual){const r=rank[n];if(r<=5)hits[0]++;if(r<=10)hits[1]++;if(r<=20)hits[2]++;}
  if(hits[0]!==Number(f[ix.hit5])||hits[1]!==Number(f[ix.hit10])||hits[2]!==Number(f[ix.hit20]))errors++;
  g.ids.add(f[ix.id]);g.cfg.push(rank);
}
if(g)groups.push(g);
for(const x of groups){
  if(x.cfg.length!==42||x.ids.size!==42||x.actual.length!==5||new Set(x.actual).size!==5||
     x.actual.some(n=>n<1||n>40))errors++;
}
assert(errors===0,'source row validation errors: '+errors);
assert(groups.length===3204&&lines.length-1===134568,'source row/target counts mismatch');

const splitDefs=[{name:'discovery',a:0,z:1922},{name:'validation',a:1922,z:2563},{name:'blind_oos',a:2563,z:3204}];
const ks=[5,10,20],obs=ks.map(()=>new Int8Array(groups.length));
for(let t=0;t<groups.length;t++){
  for(let j=0;j<42;j++){
    let c5=0,c10=0,c20=0;const r=groups[t].cfg[j];
    for(const n of groups[t].actual){const q=r[n];if(q<=5)c5++;if(q<=10)c10++;if(q<=20)c20++;}
    if(c5>obs[0][t])obs[0][t]=c5;
    if(c10>obs[1][t])obs[1][t]=c10;
    if(c20>obs[2][t])obs[2][t]=c20;
  }
}
let state=0x01302026>>>0;
const rng=()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return state>>>0;};
const limit40=Math.floor(4294967296/40)*40;
const uniform40=()=>{let v;do{v=rng();}while(v>=limit40);return v%40+1;};
const draw=()=>{const a=[];while(a.length<5){const n=uniform40();if(!a.includes(n))a.push(n);}return a;};
const B=1000,sumPer=ks.map(()=>new Float64Array(groups.length));
const nullMeans=ks.map(()=>splitDefs.map(()=>new Float64Array(B)));
for(let rep=0;rep<B;rep++){
  const splitSums=ks.map(()=>[0,0,0]);
  for(let t=0;t<groups.length;t++){
    const d=draw();let m5=0,m10=0,m20=0;
    for(let j=0;j<42;j++){
      let c5=0,c10=0,c20=0;const r=groups[t].cfg[j];
      for(const n of d){const q=r[n];if(q<=5)c5++;if(q<=10)c10++;if(q<=20)c20++;}
      if(c5>m5)m5=c5;if(c10>m10)m10=c10;if(c20>m20)m20=c20;
      if(m5===5)break;
    }
    const v=[m5,m10,m20],s=t<1922?0:t<2563?1:2;
    for(let k=0;k<3;k++){sumPer[k][t]+=v[k];splitSums[k][s]+=v[k];}
  }
  for(let k=0;k<3;k++)for(let s=0;s<3;s++)nullMeans[k][s][rep]=splitSums[k][s]/(splitDefs[s].z-splitDefs[s].a);
}
const splitReport={};
for(let k=0;k<3;k++)for(let s=0;s<3;s++){
  const d=splitDefs[s],v=Array.from(obs[k].slice(d.a,d.z)),nm=Array.from(nullMeans[k][s]);
  const om=v.reduce((a,b)=>a+b,0)/v.length;
  const nn=sumPer[k].slice(d.a,d.z).reduce((a,b)=>a+b,0)/(B*v.length);
  const dist={0:0,1:0,2:0,3:0,4:0,5:0};for(const x of v)dist[x]++;
  const sorted=nm.slice().sort((a,b)=>a-b),ge=nm.filter(x=>x>=om).length;
  if(!splitReport[d.name])splitReport[d.name]={targets:v.length,first_target:groups[d.a].date,last_target:groups[d.z-1].date,endpoints:{}};
  splitReport[d.name].endpoints['top'+ks[k]]={
    mean_max_hits:round(om),observed_distribution:dist,conditional_null_mean:round(nn),
    mean_gain:round(om-nn),randomization_p_upper:Number(((ge+1)/(B+1)).toFixed(6)),
    conditional_null_mean_95_interval:[round(sorted[24]),round(sorted[974])]
  };
}
let bs=0x01312026>>>0;
const brng=()=>{bs^=bs<<13;bs^=bs>>>17;bs^=bs<<5;return bs>>>0;};
const limit641=Math.floor(4294967296/641)*641;
const uniform641=()=>{let v;do{v=brng();}while(v>=limit641);return v%641;};
const infer={};
for(let k=0;k<3;k++){
  const dif=Array.from({length:641},(_,i)=>obs[k][2563+i]-sumPer[k][2563+i]/B);
  const boot=new Float64Array(10000);
  for(let b=0;b<10000;b++){
    let s=0,n=0;
    while(n<641){const start=uniform641();for(let j=0;j<20&&n<641;j++){s+=dif[(start+j)%641];n++;}}
    boot[b]=s/641;
  }
  boot.sort();
  const key='top'+ks[k],om=splitReport.blind_oos.endpoints[key].mean_max_hits,nn=splitReport.blind_oos.endpoints[key].conditional_null_mean;
  infer[key]={
    observed_mean:om,conditional_null_mean:nn,mean_gain:round(om-nn),
    randomization_p_raw:splitReport.blind_oos.endpoints[key].randomization_p_upper,
    holm_adjusted_p:null,
    block_bootstrap:{replicates:10000,block_length:20,mean_gain:round(dif.reduce((a,b)=>a+b,0)/641),ci95:[round(boot[249]),round(boot[9749])]}
  };
}
const pSorted=Object.entries(infer).map(([k,v])=>({k,p:v.randomization_p_raw})).sort((a,b)=>a.p-b.p);
let cum=0;for(let i=0;i<pSorted.length;i++){cum=Math.max(cum,Math.min(1,(pSorted.length-i)*pSorted[i].p));infer[pSorted[i].k].holm_adjusted_p=Number(cum.toFixed(6));}

const provPath=P+'q130_contest_315_provisional_observation_2026-11-11.json';
const prov=JSON.parse(read(provPath));
assert(prov.status==='PROVISIONAL_SECONDARY_SOURCE_CORROBORATED'&&prov.target_date==='2026-11-11','provisional contest 315 status mismatch');
const den=prov.scoring.exact_familywise_null.denominator,ds=prov.scoring.exact_familywise_null.distribution_max_hits;
const p315={top5:{observed_max_hits:prov.scoring.global_rule_family.top5_max},top10:{observed_max_hits:prov.scoring.global_rule_family.top10_max},top20:{observed_max_hits:prov.scoring.global_rule_family.top20_max}};
for(const [k,di,si] of [['top20',0,0],['top10',1,1],['top5',2,2]]){
  const o=p315[k].observed_max_hits;
  const tail=Object.entries(ds[di]).filter(([h])=>Number(h)>=o).reduce((s,[,v])=>s+v,0)/den;
  assert(Math.abs(tail-prov.scoring.exact_familywise_null.p_familywise_tail_at_observed[si])<1e-12,'provisional exact tail mismatch '+k);
  p315[k].exact_familywise_tail=round(tail);
}
const report=JSON.parse(read(P+'q130_familywise_topk_depth_report_2026-11-12.json'));
for(const d of splitDefs)for(let k=0;k<3;k++){
  const saved=report.splits[d.name].endpoints['top'+ks[k]],actual=splitReport[d.name].endpoints['top'+ks[k]];
  for(const key of ['mean_max_hits','conditional_null_mean','mean_gain','randomization_p_upper']){
    assert(saved[key]===actual[key],'report mismatch '+d.name+' '+ks[k]+' '+key);
  }
  assert(JSON.stringify(saved.observed_distribution)===JSON.stringify(actual.observed_distribution),'distribution mismatch '+d.name+' '+ks[k]);
}
for(const k of ['top5','top10','top20']){
  const a=report.primary_inference.endpoints[k],b=infer[k];
  for(const key of ['observed_mean','conditional_null_mean','mean_gain','randomization_p_raw','holm_adjusted_p'])assert(a[key]===b[key],'inference mismatch '+k+' '+key);
  assert(JSON.stringify(a.block_bootstrap.ci95)===JSON.stringify(b.block_bootstrap.ci95),'bootstrap CI mismatch '+k);
}
assert(report.decision==='NO_FAMILYWISE_TOPK_DEPTH_LIFT_DEMONSTRATED','decision mismatch');
for(const k of ['top5','top10','top20'])assert(report.prospective_observation.exact_familywise_tail[k]===p315[k].exact_familywise_tail,'provisional tail report mismatch '+k);

const ledger=['target_date,history_cutoff,rule_configurations,observed_max_top5_hits,null_expected_max_top5_hits,gain_top5,observed_max_top10_hits,null_expected_max_top10_hits,gain_top10,observed_max_top20_hits,null_expected_max_top20_hits,gain_top20,split'];
for(let t=0;t<groups.length;t++){
  const split=t<1922?'discovery':t<2563?'validation':'blind_oos',vals=[];
  for(let k=0;k<3;k++){const e=sumPer[k][t]/B;vals.push(obs[k][t],e.toFixed(8),(obs[k][t]-e).toFixed(8));}
  ledger.push([groups[t].date,groups[t].cut,42,...vals,split].join(','));
}
assert(read(P+'q130_familywise_topk_depth_target_ledger_2026-11-12.csv')===ledger.join('\n')+'\n','target ledger replay mismatch');

const validation=JSON.parse(read(P+'q130_familywise_topk_depth_validation_2026-11-12.json'));
assert(validation.status==='PASS'&&validation.checks_passed===20&&validation.checks_total===20&&validation.checks.every(x=>x.passed===true),'validation JSON mismatch');
const archive=read('data/storico_daily.csv').trimEnd().split(/\r?\n/);
const metrics=JSON.parse(read(P+'latest_metrics.json'));
const gate=JSON.parse(read(P+'prospective_promotion_gate.json'));
assert(archive.length-1===3404&&archive[archive.length-1].startsWith('2026-11-10,'),'canonical archive cutoff changed');
assert(metrics.total_draws===3404&&metrics.data_last_date==='2026-11-10','latest metrics cutoff mismatch');
assert(gate.status==='INSUFFICIENT_PROSPECTIVE_CASES'&&gate.valid_complete_prospective_targets===23&&gate.minimum_required===200,'Q60 gate changed');
assert(report.prospective_observation.canonical_archive_updated===false&&report.prospective_observation.q60_incremented===false,'provisional result improperly canonicalized');
assert(report.decision==='NO_FAMILYWISE_TOPK_DEPTH_LIFT_DEMONSTRATED','unexpected engine-promotion decision');

const checkpoint=read(P+'q130_familywise_topk_depth_checkpoint_2026-11-12.md');
assert(checkpoint.includes('NO_FAMILYWISE_TOPK_DEPTH_LIFT_DEMONSTRATED')&&checkpoint.includes('Q60 increment')&&checkpoint.includes('0.75025'),'checkpoint mismatch');

const manifest=JSON.parse(read(P+'q130_familywise_topk_depth_persistence_manifest_2026-11-12.json'));
assert(manifest.entries.length===8,'manifest entry count mismatch');
for(const e of manifest.entries){
  const actual=execFileSync('git',['rev-parse','HEAD:'+e.path],{encoding:'utf8'}).trim();
  assert(actual===e.git_blob_sha,'manifest Git blob SHA mismatch: '+e.path);
  assert(Buffer.byteLength(read(e.path),'utf8')===e.bytes_utf8,'manifest UTF-8 byte count mismatch: '+e.path);
}
console.log('Q130 CHECK PASS: 3,204 targets; 134,568 source rows; 42 fixed configurations; Top5/Top10/Top20 family-wise maxima; 1,000 unbiased conditional randomizations; 10,000 paired block-bootstrap replicates; Holm family size 3; provisional contest 315 kept outside canonical history; ledger replay matched; manifest 8/8 verified.');
