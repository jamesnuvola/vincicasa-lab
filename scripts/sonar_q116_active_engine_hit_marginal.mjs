import fs from "node:fs";
import crypto from "node:crypto";
const ROOT = process.cwd();
const SRC = ROOT + "/reports/sequence_agent/q116_source_active_engine_hit_sequence_2026-11-11.csv";
const REPORT = ROOT + "/reports/sequence_agent/q116_active_engine_hit_marginal_report_2026-11-11.json";
const VALID = ROOT + "/reports/sequence_agent/q116_active_engine_hit_marginal_validation_2026-11-11.json";
const EXPECTED_SOURCE_SHA = "b4ea460d0080f7abbec0b4d563a6089a3146fff5";
const Q113_SOURCE_SHA = "79ad1092d71c4c93aa7365bcd4e8ee48d42df569";
const round = x => Math.abs(x) < 5e-13 ? 0 : Number(x.toFixed(12));
function gitBlobSha(content) {
  const b = Buffer.from(content, "utf8");
  return crypto.createHash("sha1").update(Buffer.concat([Buffer.from("blob " + b.length + "\0"), b])).digest("hex");
}
function parseCsv(text) {
  const lines = text.trimEnd().split(/\r?\n/);
  const header = lines.shift().split(",");
  return lines.map(line => {
    const values = line.split(",");
    if (values.length !== header.length) throw new Error("CSV width mismatch");
    return Object.fromEntries(header.map((key, i) => [key, values[i]]));
  });
}
function choose(n, k) {
  if (k < 0 || k > n) return 0;
  let value = 1;
  for (let i = 1; i <= k; i++) value = value * (n - k + i) / i;
  return value;
}
const q0 = Array.from({length: 6}, (_, k) => choose(20, k) * choose(20, 5-k) / choose(40, 5));
const nullVariance = 5 * 0.5 * 0.5 * 35 / 39;
function logGamma(z) {
  const p = [676.5203681218851,-1259.1392167224028,771.3234287776531,-176.6150291621406,12.507343278686905,-0.13857109526572012,9.984369578019572e-6,1.5056327351493116e-7];
  if (z < 0.5) return Math.log(Math.PI) - Math.log(Math.sin(Math.PI*z)) - logGamma(1-z);
  z -= 1;
  let x = 0.99999999999980993;
  for (let i = 0; i < p.length; i++) x += p[i] / (z + i + 1);
  const t = z + p.length - 0.5;
  return 0.5 * Math.log(2*Math.PI) + (z+0.5)*Math.log(t) - t + Math.log(x);
}
function gammaQ(a, x) {
  const gln = logGamma(a), eps = 3e-14, fpmin = 1e-300, max = 10000;
  if (x === 0) return 1;
  if (x < a + 1) {
    let ap = a, sum = 1/a, del = sum;
    for (let n = 1; n < max; n++) { ap++; del *= x/ap; sum += del; if (Math.abs(del) < Math.abs(sum)*eps) break; }
    return Math.max(0, Math.min(1, 1 - sum*Math.exp(-x + a*Math.log(x) - gln)));
  }
  let b = x + 1 - a, c = 1/fpmin, d = 1/b, h = d;
  for (let i = 1; i < max; i++) {
    const an = -i * (i-a);
    b += 2; d = an*d + b; if (Math.abs(d) < fpmin) d = fpmin;
    c = b + an/c; if (Math.abs(c) < fpmin) c = fpmin;
    d = 1/d; const delta = d*c; h *= delta; if (Math.abs(delta-1) < eps) break;
  }
  return Math.max(0, Math.min(1, Math.exp(-x + a*Math.log(x) - gln)*h));
}
function erf(x) {
  const sign = x < 0 ? -1 : 1; x = Math.abs(x);
  const t = 1 / (1 + 0.3275911*x);
  const y = 1 - (((((1.061405429*t - 1.453152027)*t) + 1.421413741)*t - 0.284496736)*t + 0.254829592)*t*Math.exp(-x*x);
  return sign*y;
}
function normalTwoSided(z) { return 2 * (1 - 0.5*(1 + erf(Math.abs(z)/Math.SQRT2))); }
function binomialUpperTail(n, k, p) {
  let term = Math.pow(1-p, n), sum = 0;
  for (let i = 0; i <= n; i++) {
    if (i >= k) sum += term;
    if (i < n) term *= ((n-i)/(i+1)) * (p/(1-p));
  }
  return sum;
}
function random(seed) {
  let x = seed >>> 0;
  return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return (x >>> 0) / 4294967296; };
}
function bootstrap(values, seed) {
  const n = values.length, block = 20, reps = 10000, rand = random(seed), means = [], rates = [];
  for (let r = 0; r < reps; r++) {
    let sum = 0, five = 0, got = 0;
    while (got < n) {
      const start = Math.floor(rand()*n);
      for (let j = 0; j < block && got < n; j++, got++) {
        const v = values[(start+j)%n]; sum += v; if (v === 5) five++;
      }
    }
    means.push(sum/n); rates.push(five/n);
  }
  means.sort((a,b)=>a-b); rates.sort((a,b)=>a-b);
  return {replicates:reps,block_length:block,mean_ci95:[round(means[249]),round(means[9749])],five_rate_ci95:[round(rates[249]),round(rates[9749])]};
}
function holm(tests) {
  const sorted = tests.map(x=>({...x})).sort((a,b)=>a.p_value-b.p_value);
  let running = 0;
  for (let i=0;i<sorted.length;i++) { running = Math.max(running, Math.min(1,(sorted.length-i)*sorted[i].p_value)); sorted[i].holm_adjusted = round(running); }
  const map = new Map(sorted.map(x=>[x.key,x.holm_adjusted]));
  return tests.map(x=>({...x,holm_adjusted:map.get(x.key)}));
}
function summarize(group, seed) {
  const values = group.map(r=>r.actual_top20_hits), n = values.length, counts = [0,0,0,0,0,0];
  let sum=0,sum2=0,brier=0,logLoss=0;
  for (const y of values) {
    counts[y]++; sum+=y; sum2+=y*y; logLoss-=Math.log(q0[y]);
    for (let k=0;k<6;k++) brier += (q0[k]-(k===y?1:0))**2;
  }
  const mean=sum/n, variance=(sum2-n*mean*mean)/(n-1);
  const pearson=counts.reduce((z,c,k)=>z+(c-n*q0[k])**2/(n*q0[k]),0);
  const z=(mean-2.5)/Math.sqrt(nullVariance/n), five=counts[5];
  return {
    n,counts,expected_counts:q0.map(p=>round(p*n)),
    mean_hits:round(mean),mean_gain_vs_2_5:round(mean-2.5),
    sample_variance:round(variance),null_variance:round(nullVariance),variance_ratio:round(variance/nullVariance),
    pearson_chi2:round(pearson),pearson_p:round(gammaQ(2.5,pearson/2)),
    mean_z:round(z),mean_p_two_sided:round(normalTwoSided(z)),
    five_of_five_count:five,five_of_five_rate:round(five/n),five_of_five_expected:round(n*q0[5]),
    five_of_five_binomial_p_one_sided:round(binomialUpperTail(n,five,q0[5])),
    baseline_brier:round(brier/n),baseline_log_loss:round(logLoss/n),
    bootstrap:bootstrap(values,seed)
  };
}
function compute(rows) {
  const groups = {
    discovery:rows.filter(r=>r.split==="discovery"),
    validation:rows.filter(r=>r.split==="validation"),
    blind_oos:rows.filter(r=>r.split==="blind_oos"),
    full:rows
  };
  const summaries = {}, tests = [];
  const names = Object.keys(groups);
  names.forEach((name,i)=>{
    const s=summarize(groups[name],11611+i);
    summaries[name]=s;
    tests.push({key:name+"_pearson",segment:name,endpoint:"pearson_chi2",p_value:s.pearson_p});
    tests.push({key:name+"_mean",segment:name,endpoint:"mean",p_value:s.mean_p_two_sided});
    tests.push({key:name+"_five_of_five",segment:name,endpoint:"five_of_five",p_value:s.five_of_five_binomial_p_one_sided});
  });
  const adjusted=holm(tests);
  for (const name of names) {
    summaries[name].holm = {
      pearson:adjusted.find(x=>x.key===name+"_pearson").holm_adjusted,
      mean:adjusted.find(x=>x.key===name+"_mean").holm_adjusted,
      five_of_five:adjusted.find(x=>x.key===name+"_five_of_five").holm_adjusted
    };
    delete summaries[name].pearson_p;
    delete summaries[name].mean_p_two_sided;
    delete summaries[name].five_of_five_binomial_p_one_sided;
  }
  return {summaries,tests:adjusted};
}
const sourceText=fs.readFileSync(SRC,"utf8");
if (gitBlobSha(sourceText)!==EXPECTED_SOURCE_SHA) throw new Error("Compact source Git blob SHA mismatch");
const rows=parseCsv(sourceText).map(r=>({...r,previous_top20_hits:Number(r.previous_top20_hits),actual_top20_hits:Number(r.actual_top20_hits)}));
if (rows.length!==3203) throw new Error("Expected 3,203 rows");
const dates=rows.map(r=>r.target_date);
const splitCounts={discovery:1921,validation:641,blind_oos:641};
const counts={discovery:rows.filter(r=>r.split==="discovery").length,validation:rows.filter(r=>r.split==="validation").length,blind_oos:rows.filter(r=>r.split==="blind_oos").length};
const chronological=dates.every((d,i)=>i===0||dates[i-1]<d);
const strictPrior=rows.every(r=>r.history_cutoff<r.target_date);
const lagChain=rows.slice(1).every((r,i)=>r.previous_top20_hits===rows[i].actual_top20_hits);
const range=rows.every(r=>Number.isInteger(r.actual_top20_hits)&&r.actual_top20_hits>=0&&r.actual_top20_hits<=5);
const splitOrder=rows.every((r,i)=>i<1921?r.split==="discovery":i<2562?r.split==="validation":r.split==="blind_oos");
const prefixDigest=(data,end)=>{const c=[0,0,0,0,0,0];let s=0;for(let i=0;i<end;i++){c[data[i].actual_top20_hits]++;s+=data[i].actual_top20_hits;}return c.join(",")+"|"+s;};
let futureMutation=0;
for(let j=1;j<=9;j++){const end=Math.floor(rows.length*j/10);const mutated=rows.map((r,i)=>i<end?r:{...r,actual_top20_hits:(r.actual_top20_hits+1)%6});if(prefixDigest(rows,end)===prefixDigest(mutated,end))futureMutation++;}
const resultA=compute(rows), resultB=compute(rows);
if (JSON.stringify(resultA)!==JSON.stringify(resultB)) throw new Error("Deterministic replay failed");
const report=JSON.parse(fs.readFileSync(REPORT,"utf8"));
if (JSON.stringify(report.results)!==JSON.stringify(resultA.summaries) || JSON.stringify(report.inference.tests)!==JSON.stringify(resultA.tests)) throw new Error("Report replay mismatch");
const validation=JSON.parse(fs.readFileSync(VALID,"utf8"));
const checks=[
  sourceText.startsWith("target_date,history_cutoff,previous_top20_hits,actual_top20_hits,split\n"),
  rows.length===3203,
  new Set(dates).size===rows.length,
  chronological,
  strictPrior,
  lagChain,
  range,
  counts.discovery===splitCounts.discovery&&counts.validation===splitCounts.validation&&counts.blind_oos===splitCounts.blind_oos,
  splitOrder,
  Math.abs(q0.reduce((a,b)=>a+b,0)-1)<1e-15,
  Object.values(resultA.summaries).every(s=>Math.min(...s.expected_counts)>=5),
  futureMutation===9,
  JSON.stringify(resultA)===JSON.stringify(resultB),
  validation.passed===true&&validation.checks_passed===14&&validation.checks_total===14
];
if (!checks.every(Boolean)) throw new Error("Q116 validation checks failed: "+checks.filter(Boolean).length+"/14");
console.log(JSON.stringify({
  experiment_id:"Q116",targets:rows.length,split_counts:counts,
  source_git_blob_sha:gitBlobSha(sourceText),
  future_suffix_mutation:futureMutation+"/9",
  deterministic_replay:"PASS",report_replay:"BYTE_VALUE_IDENTICAL",
  validation_checks:checks.filter(Boolean).length+"/14",
  blind_oos:{
    mean_hits:resultA.summaries.blind_oos.mean_hits,
    pearson_p:resultA.summaries.blind_oos.pearson_p,
    pearson_holm:resultA.summaries.blind_oos.holm.pearson,
    five_of_five_count:resultA.summaries.blind_oos.five_of_five_count,
    five_of_five_p:resultA.summaries.blind_oos.five_of_five_binomial_p_one_sided,
    five_of_five_holm:resultA.summaries.blind_oos.holm.five_of_five
  }
}));
