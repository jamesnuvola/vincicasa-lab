import fs from 'node:fs';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
const P='reports/sequence_agent/';
const read=(p)=>fs.readFileSync(p,'utf8');
const sha=(s)=>{const b=Buffer.from(s,'utf8');return crypto.createHash('sha1').update(Buffer.concat([Buffer.from('blob '+b.length+'\0'),b])).digest('hex');};
const json=(x)=>JSON.stringify(x,null,2)+'\n';
const round=(x,n=8)=>Number(x.toFixed(n));
const nums=(s)=>s.trim().split(/\s+/).map(Number);
const mask=(s)=>{let l=0,u=0;for(const z of s.trim().split(/\s+/)){const n=Number(z);if(n<=32)l|=1<<(n-1);else u|=1<<(n-33);}return [l>>>0,u>>>0];};
const pop=(x)=>{x=x-((x>>>1)&0x55555555);x=(x&0x33333333)+((x>>>2)&0x33333333);return (((x+(x>>>4))&0x0f0f0f0f)*0x01010101)>>>24;};
const csv=(s)=>s.trimEnd().split(/\r?\n/).map(x=>x.split(','));
const protocolPath=P+'q129_familywise_max_hit_audit_protocol_2026-11-11.json';
const protocolText=read(protocolPath),protocol=JSON.parse(protocolText);
const sourcePath='reports/sequence_agent/historical_rule_ledger.csv';
const committedSourceBlob=execFileSync('git',['rev-parse',`HEAD:${sourcePath}`],{encoding:'utf8'}).trim();
if(committedSourceBlob!==protocol.source.git_blob_sha)throw new Error('source Git tree blob SHA mismatch: '+committedSourceBlob);
try{execFileSync('git',['diff','--quiet','HEAD','--',sourcePath],{stdio:'ignore'});}catch{throw new Error('source working-tree content differs from committed Git blob');}
const sourceText=read(sourcePath);
const lines=csv(sourceText),h=lines[0],ix={d:h.indexOf('target_date'),c:h.indexOf('history_cutoff'),id:h.indexOf('config_id'),t:h.indexOf('top20'),a:h.indexOf('actual_numbers'),hit:h.indexOf('hit_count'),mode:h.indexOf('evaluation_mode')};
const groups=[];let g=null,errors=0;
for(let i=1;i<lines.length;i++){const f=lines[i];if(!g||g.date!==f[ix.d]){if(g)groups.push(g);g={date:f[ix.d],cut:f[ix.c],actual:f[ix.a],am:mask(f[ix.a]),cfg:[],ids:new Set()};}
 const ns=nums(f[ix.t]),m=mask(f[ix.t]);if(g.cut>=g.date||g.actual!==f[ix.a]||g.ids.has(f[ix.id])||ns.length!==20||new Set(ns).size!==20||ns.some(n=>n<1||n>40))errors++;
 if(pop(g.am[0]&m[0])+pop(g.am[1]&m[1])!==Number(f[ix.hit])||f[ix.mode]!==protocol.source.evaluation_mode)errors++;
 g.ids.add(f[ix.id]);g.cfg.push(m);}
if(g)groups.push(g);
for(const x of groups){const a=nums(x.actual);if(x.cfg.length!==42||x.ids.size!==42||a.length!==5||new Set(a).size!==5||a.some(n=>n<1||n>40))errors++;x.obs=Math.max(...x.cfg.map(m=>pop(x.am[0]&m[0])+pop(x.am[1]&m[1])));}
if(errors||groups.length!==3204||lines.length-1!==134568)throw new Error('historical source validation failed: '+errors);
const splits={discovery:[0,1922],validation:[1922,2563],blind_oos:[2563,3204]},observed={};
for(const [k,[a,z]] of Object.entries(splits)){const v=groups.slice(a,z).map(x=>x.obs),d={};for(let n=0;n<=5;n++)d[n]=v.filter(x=>x===n).length;observed[k]={mean:v.reduce((s,x)=>s+x,0)/v.length,dist:d,first:groups[a].date,last:groups[z-1].date};}
let state=Number.parseInt(protocol.design.randomization_seed.slice(2),16)>>>0;
const rng=()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return state>>>0;};
const draw=()=>{let l=0,u=0,n=0;while(n<5){const k=rng()%40;if(k<32){const b=(1<<k)>>>0;if(!(l&b)){l=(l|b)>>>0;n++;}}else{const b=(1<<(k-32))>>>0;if(!(u&b)){u=(u|b)>>>0;n++;}}}return [l,u];};
const B=protocol.design.randomization_replicates,sum=new Float64Array(groups.length),nullMeans={discovery:[],validation:[],blind_oos:[]};
for(let r=0;r<B;r++){const ss={discovery:0,validation:0,blind_oos:0};for(let t=0;t<groups.length;t++){const d=draw();let mx=0;for(const m of groups[t].cfg){const v=pop(d[0]&m[0])+pop(d[1]&m[1]);if(v>mx)mx=v;if(mx===5)break;}sum[t]+=mx;if(t<1922)ss.discovery+=mx;else if(t<2563)ss.validation+=mx;else ss.blind_oos+=mx;}nullMeans.discovery.push(ss.discovery/1922);nullMeans.validation.push(ss.validation/641);nullMeans.blind_oos.push(ss.blind_oos/641);}
const per=sum.map(x=>x/B),inf={};
for(const [k,[a,z]] of Object.entries(splits)){const nm=per.slice(a,z).reduce((s,x)=>s+x,0)/(z-a),arr=nullMeans[k],sorted=arr.slice().sort((x,y)=>x-y),ge=arr.filter(x=>x>=observed[k].mean).length;inf[k]={observed_mean:round(observed[k].mean),null_mean:round(nm),gain:round(observed[k].mean-nm),p_upper:Number(((ge+1)/(B+1)).toFixed(6)),null95:[round(sorted[25]),round(sorted[975])]};}
let bs=Number.parseInt(protocol.design.bootstrap.seed.slice(2),16)>>>0;
const br=()=>{bs^=bs<<13;bs^=bs>>>17;bs^=bs<<5;return bs>>>0;};
const dif=groups.slice(2563).map((x,i)=>x.obs-per[2563+i]),boot=[];
for(let r=0;r<protocol.design.bootstrap.replicates;r++){let s=0,n=0;while(n<641){const start=br()%641;for(let j=0;j<protocol.design.bootstrap.block_length&&n<641;j++){s+=dif[(start+j)%641];n++;}}boot.push(s/641);}
boot.sort((a,b)=>a-b);
const bootSummary={replicates:boot.length,block_length:protocol.design.bootstrap.block_length,mean_gain:round(dif.reduce((s,x)=>s+x,0)/641),ci95:[round(boot[249]),round(boot[9749])]};
const report=JSON.parse(read(P+'q129_familywise_max_hit_audit_report_2026-11-11.json'));
for(const k of Object.keys(splits)){const r=report.splits[k];if(Math.abs(r.mean_max_hits-round(observed[k].mean))>1e-8||Math.abs(r.conditional_null_mean-inf[k].null_mean)>1e-8||Math.abs(r.mean_gain-inf[k].gain)>1e-8||Math.abs(r.randomization_p_upper-inf[k].p_upper)>1e-6)throw new Error('report mismatch '+k);}
if(Math.abs(report.primary_inference.block_bootstrap.mean_gain-bootSummary.mean_gain)>1e-8||JSON.stringify(report.primary_inference.block_bootstrap.ci95)!==JSON.stringify(bootSummary.ci95))throw new Error('bootstrap mismatch');
const ledger=['target_date,history_cutoff,rule_configurations,observed_max_top20_hits,null_expected_max_top20_hits,gain_vs_null,split'];
for(let i=0;i<groups.length;i++){const split=i<1922?'discovery':i<2563?'validation':'blind_oos';ledger.push([groups[i].date,groups[i].cut,42,groups[i].obs,per[i].toFixed(8),(groups[i].obs-per[i]).toFixed(8),split].join(','));}
const ledgerText=ledger.join('\n')+'\n';
if(read(P+'q129_familywise_max_hit_audit_target_ledger_2026-11-11.csv')!==ledgerText)throw new Error('target ledger replay mismatch');
const provisional=JSON.parse(read(P+'q129_contest_315_provisional_observation_2026-11-11.json'));
const sh=csv(read('reports/sequence_agent/shadow_forecasts.csv')),shh=sh[0],sx={d:shh.indexOf('target_date'),id:shh.indexOf('config_id'),type:shh.indexOf('config_type'),t20:shh.indexOf('top20'),t10:shh.indexOf('top10'),t5:shh.indexOf('top5')};
const sr=sh.slice(1).filter(x=>x[sx.d]==='2026-11-11'),rules=sr.filter(x=>x[sx.type]!=='app_engine'),app=sr.find(x=>x[sx.type]==='app_engine');
const pl=csv(read('reports/sequence_agent/position_mix_shadow.csv')),ph=pl[0],px={d:ph.indexOf('target_date'),t20:ph.indexOf('top20'),t10:ph.indexOf('top10'),t5:ph.indexOf('top5')},pos=pl.slice(1).find(x=>x[px.d]==='2026-11-11');
if(sr.length!==43||rules.length!==42||!app||!pos)throw new Error('prospective freeze rows missing');
const win=provisional.result_numbers,ws=new Set(win),hit=(s)=>nums(s).filter(n=>ws.has(n)).sort((a,b)=>a-b);
const scores={result_numbers:win,global_rule_family_count:42,global_rule_family:{top20_max:Math.max(...rules.map(x=>hit(x[sx.t20]).length)),top10_max:Math.max(...rules.map(x=>hit(x[sx.t10]).length)),top5_max:Math.max(...rules.map(x=>hit(x[sx.t5]).length)),best_top20_configs:rules.filter(x=>hit(x[sx.t20]).length===5).map(x=>x[sx.id])},app_engine:{top20_hits:hit(app[sx.t20]),top10_hits:hit(app[sx.t10]),top5_hits:hit(app[sx.t5])},positional_engine:{top20_hits:hit(pos[px.t20]),top10_hits:hit(pos[px.t10]),top5_hits:hit(pos[px.t5])}};
const fam=[0,1,2].map(k=>rules.map(x=>mask(x[[sx.t20,sx.t10,sx.t5][k]]))),dist=[{},{},{}],N=658008;
for(let a=1;a<=36;a++)for(let b=a+1;b<=37;b++)for(let c=b+1;c<=38;c++)for(let d=c+1;d<=39;d++)for(let e=d+1;e<=40;e++){let l=0,u=0;for(const n of [a,b,c,d,e]){if(n<=32)l|=1<<(n-1);else u|=1<<(n-33);}for(let k=0;k<3;k++){let mx=0;for(const m of fam[k]){const v=pop((l>>>0)&m[0])+pop((u>>>0)&m[1]);if(v>mx)mx=v;if(mx===5)break;}dist[k][mx]=(dist[k][mx]||0)+1;}}
const mx=[scores.global_rule_family.top20_max,scores.global_rule_family.top10_max,scores.global_rule_family.top5_max],tails=[0,1,2].map(k=>Object.entries(dist[k]).filter(([n])=>Number(n)>=mx[k]).reduce((s,[,v])=>s+v,0)/N);
scores.exact_familywise_null={denominator:N,distribution_max_hits:dist,p_familywise_tail_at_observed:tails,note:'Exact enumeration of all 658,008 5-of-40 outcomes, preserving overlap among the 42 fixed forecast sets.'};
if(JSON.stringify(provisional.scoring)!==JSON.stringify(scores))throw new Error('provisional freeze scoring mismatch');
const validation=JSON.parse(read(P+'q129_familywise_max_hit_audit_validation_2026-11-11.json'));
if(validation.checks_passed!==12||validation.checks_total!==12||validation.checks.some(x=>!x.passed))throw new Error('validation status mismatch');
if(report.decision!=='NO_FAMILYWISE_MAX_HIT_LIFT_DEMONSTRATED'||provisional.canonical_archive_updated||provisional.q60.incremented)throw new Error('governance guardrail mismatch');
const manifest=JSON.parse(read(P+'q129_familywise_max_hit_audit_persistence_manifest_2026-11-11.json'));
for(const e of manifest.entries){const value=read(e.path);if(gitBlobSha(value)!==e.git_blob_sha||Buffer.byteLength(value,'utf8')!==e.bytes_utf8)throw new Error('manifest mismatch '+e.path);}
if(manifest.entries.length!==8)throw new Error('manifest entry count mismatch');
console.log('Q129 CHECK PASS: 3,204 targets; 134,568 source rows; 42 configurations per target; 1,000 conditional randomization replicates; 10,000 block-bootstrap replicates; exact 658,008-outcome prospective family-wise audit; report/ledger replay matched; manifest '+manifest.entries.length+'/8 verified.');
