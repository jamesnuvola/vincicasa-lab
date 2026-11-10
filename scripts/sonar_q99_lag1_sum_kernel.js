function runQ99(csvText) {
  const ALPHA = 200;
  const BANDWIDTHS = [0.25, 0.5, 1.0, 2.0];
  const WARMUP = 300;
  const DISCOVERY_N = 1400;
  const VALIDATION_N = 850;
  const BOOT_REPS = 10000;
  const SIGNFLIP_REPS = 50000;
  const BLOCK = 20;
  const MIN_SUM = 15;
  const MAX_SUM = 190;
  const CATS = MAX_SUM - MIN_SUM + 1;
  const EXPECTED_SUBSETS = 658008;

  function fail(message) { throw new Error("Q99: " + message); }
  function mean(a) { return a.reduce((s, x) => s + x, 0) / a.length; }
  function parseArchive(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < WARMUP + 2) fail("archive too short");
    const header = lines[0].split(",");
    if (header.join(",") !== "data,n1,n2,n3,n4,n5") fail("unexpected archive header");
    const draws = [];
    const dates = [];
    for (let i = 1; i < lines.length; i++) {
      const f = lines[i].split(",");
      if (f.length !== 6) fail("malformed row " + i);
      const d = f[0];
      const ns = f.slice(1).map(Number);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) fail("invalid date " + d);
      if (ns.some(x => !Number.isInteger(x) || x < 1 || x > 40)) fail("invalid number at row " + i);
      if (new Set(ns).size !== 5 || ns.some((x,j) => j && ns[j-1] >= x)) fail("draw not strictly sorted unique at row " + i);
      if (i > 1 && !(dates[i-2] < d)) fail("dates not strictly increasing");
      dates.push(d);
      draws.push(ns);
    }
    return {dates, draws, sums:draws.map(a => a.reduce((s,x)=>s+x,0))};
  }
  function exactNull() {
    const dp = Array.from({length:6},()=>new Float64Array(MAX_SUM+1));
    dp[0][0] = 1;
    for (let n=1;n<=40;n++) {
      for (let k=5;k>=1;k--) {
        for (let s=MAX_SUM;s>=n;s--) dp[k][s] += dp[k-1][s-n];
      }
    }
    const counts = dp[5];
    const total = counts.reduce((s,x)=>s+x,0);
    if (total !== EXPECTED_SUBSETS) fail("exact subset count mismatch: " + total);
    const p = Array.from({length:CATS},(_,i)=>counts[i+MIN_SUM]/total);
    const pSum = p.reduce((s,x)=>s+x,0);
    if (Math.abs(pSum-1)>1e-15) fail("exact null does not normalize");
    let mu=0, second=0, sumSq=0;
    for (let i=0;i<CATS;i++) {
      const s=i+MIN_SUM;
      mu += s*p[i];
      second += s*s*p[i];
      sumSq += p[i]*p[i];
    }
    const sd=Math.sqrt(second-mu*mu);
    return {counts:Array.from(counts),p,total,mu,sd,sumSq};
  }
  function makeRng(seed) {
    let x = seed >>> 0;
    return function() {
      x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
      return (x >>> 0) / 4294967296;
    };
  }
  function forecast(sums, t, h, nullModel) {
    const prev = sums[t-1];
    const weighted = new Float64Array(CATS);
    let weightTotal=0;
    for (let i=0;i<t-1;i++) {
      const z=(sums[i]-prev)/nullModel.sd;
      const w=Math.exp(-0.5*z*z/(h*h));
      weighted[sums[i+1]-MIN_SUM] += w;
      weightTotal += w;
    }
    const den=ALPHA+weightTotal;
    let sumP=0, sumP2=0;
    const probs=new Float64Array(CATS);
    for (let j=0;j<CATS;j++) {
      const q=(ALPHA*nullModel.p[j]+weighted[j])/den;
      probs[j]=q;
      sumP += q;
      sumP2 += q*q;
    }
    const err=Math.abs(sumP-1);
    if (err>1e-12) fail("forecast probability normalization error " + err);
    const actual=sums[t]-MIN_SUM;
    const pActual=probs[actual];
    const brier=1+sumP2-2*pActual;
    const logloss=-Math.log(pActual);
    const baselineBrier=1+nullModel.sumSq-2*nullModel.p[actual];
    const baselineLogloss=-Math.log(nullModel.p[actual]);
    return {
      brierGain:baselineBrier-brier,
      loglossGain:baselineLogloss-logloss,
      modelBrier:brier,
      modelLogloss:logloss,
      sumP,
      weightTotal
    };
  }
  function splitName(i) {
    if (i<DISCOVERY_N) return "discovery";
    if (i<DISCOVERY_N+VALIDATION_N) return "validation";
    return "blind_oos_historical";
  }
  function circularBootstrapCI(values, seed) {
    const n=values.length;
    const full=Math.floor(n/BLOCK);
    const rem=n-full*BLOCK;
    const wFull=new Float64Array(n), wRem=new Float64Array(n);
    for(let i=0;i<n;i++) {
      let a=0,b=0;
      for(let j=0;j<BLOCK;j++) a+=values[(i+j)%n];
      for(let j=0;j<rem;j++) b+=values[(i+j)%n];
      wFull[i]=a; wRem[i]=b;
    }
    const rng=makeRng(seed);
    const boot=new Array(BOOT_REPS);
    for(let r=0;r<BOOT_REPS;r++) {
      let total=0;
      for(let k=0;k<full;k++) total+=wFull[Math.floor(rng()*n)];
      if(rem) total+=wRem[Math.floor(rng()*n)];
      boot[r]=total/n;
    }
    boot.sort((a,b)=>a-b);
    return [boot[Math.floor(0.025*(BOOT_REPS-1))],boot[Math.floor(0.975*(BOOT_REPS-1))]];
  }
  function blockSignFlipP(values, seed) {
    const n=values.length, blockSums=[];
    for(let i=0;i<n;i+=BLOCK) {
      let s=0;
      for(let j=i;j<Math.min(i+BLOCK,n);j++) s+=values[j];
      blockSums.push(s);
    }
    const obs=values.reduce((s,x)=>s+x,0);
    const rng=makeRng(seed);
    let extreme=0;
    for(let r=0;r<SIGNFLIP_REPS;r++) {
      let perm=0;
      for(let b=0;b<blockSums.length;b++) perm += (rng()<0.5?-1:1)*blockSums[b];
      if(perm>=obs-1e-12) extreme++;
    }
    return (extreme+1)/(SIGNFLIP_REPS+1);
  }
  function holm(tests) {
    const order=tests.map((x,i)=>({i,p:x.raw_p})).sort((a,b)=>a.p-b.p);
    let running=0;
    const adj=new Array(tests.length);
    for(let r=0;r<order.length;r++) {
      running=Math.max(running,(tests.length-r)*order[r].p);
      adj[order[r].i]=Math.min(1,running);
    }
    return tests.map((x,i)=>({...x,holm_adjusted_p:adj[i]}));
  }

  const archive=parseArchive(csvText);
  const nullModel=exactNull();
  const nTargets=archive.draws.length-WARMUP;
  if(nTargets!==3103) fail("target count changed: "+nTargets);
  if(DISCOVERY_N+VALIDATION_N+(nTargets-DISCOVERY_N-VALIDATION_N)!==nTargets) fail("split arithmetic error");

  const rows=[];
  const byH={};
  for(const h of BANDWIDTHS) byH[String(h)]={brierGain:[],loglossGain:[],modelBrier:[],modelLogloss:[]};
  let maxNormError=0, minWeightTotal=Infinity, maxWeightTotal=0;
  for(let j=0;j<nTargets;j++) {
    const t=WARMUP+j;
    const hMetrics={};
    for(const h of BANDWIDTHS) {
      const m=forecast(archive.sums,t,h,nullModel);
      hMetrics[String(h)]=m;
      byH[String(h)].brierGain.push(m.brierGain);
      byH[String(h)].loglossGain.push(m.loglossGain);
      byH[String(h)].modelBrier.push(m.modelBrier);
      byH[String(h)].modelLogloss.push(m.modelLogloss);
      maxNormError=Math.max(maxNormError,Math.abs(m.sumP-1));
      minWeightTotal=Math.min(minWeightTotal,m.weightTotal);
      maxWeightTotal=Math.max(maxWeightTotal,m.weightTotal);
    }
    const split=splitName(j);
    const r={
      target_index:t,
      target_date:archive.dates[t],
      cutoff_date:archive.dates[t-1],
      previous_sum:archive.sums[t-1],
      actual_sum:archive.sums[t],
      prior_transition_count:t-1,
      max_training_outcome_index:t-1,
      split
    };
    for(const h of BANDWIDTHS) {
      const m=hMetrics[String(h)];
      const key=String(h).replace(".","_");
      r["brier_gain_h"+key]=m.brierGain;
      r["logloss_gain_h"+key]=m.loglossGain;
    }
    if(r.max_training_outcome_index>=r.target_index) fail("leakage boundary failed at "+r.target_date);
    rows.push(r);
  }

  const splits={};
  const splitDefs=[
    ["discovery",0,DISCOVERY_N],
    ["validation",DISCOVERY_N,DISCOVERY_N+VALIDATION_N],
    ["blind_oos_historical",DISCOVERY_N+VALIDATION_N,nTargets]
  ];
  for(const [name,start,end] of splitDefs) {
    const out={targets:end-start,bandwidths:{}};
    for(const h of BANDWIDTHS) {
      const src=byH[String(h)];
      const avg=(a)=>mean(a.slice(start,end));
      out.bandwidths[String(h)]={
        mean_brier_gain_vs_exact_null:avg(src.brierGain),
        mean_logloss_gain_vs_exact_null:avg(src.loglossGain),
        mean_model_brier:avg(src.modelBrier),
        mean_model_logloss:avg(src.modelLogloss)
      };
    }
    splits[name]=out;
  }

  let selectedH=BANDWIDTHS[0], bestGain=-Infinity;
  for(const h of BANDWIDTHS) {
    const g=splits.validation.bandwidths[String(h)].mean_brier_gain_vs_exact_null;
    if(g>bestGain+1e-15 || (Math.abs(g-bestGain)<=1e-15 && h<selectedH)) {
      bestGain=g; selectedH=h;
    }
  }

  const blindStart=DISCOVERY_N+VALIDATION_N;
  const blindTests=[];
  let testIndex=0;
  for(const h of BANDWIDTHS) {
    for(const endpoint of ["brierGain","loglossGain"]) {
      const values=byH[String(h)][endpoint].slice(blindStart);
      const observed=mean(values);
      const seed=0x99000000 + (++testIndex)*7919;
      const ci=circularBootstrapCI(values,seed);
      const p=blockSignFlipP(values,seed+31337);
      blindTests.push({
        bandwidth:h,
        endpoint:endpoint==="brierGain"?"brier_gain":"logloss_gain",
        mean_gain:observed,
        block_bootstrap_ci95:ci,
        block_signflip_p_one_sided:p,
        block_length:BLOCK,
        bootstrap_replicates:BOOT_REPS,
        signflip_replicates:SIGNFLIP_REPS,
        n:values.length
      });
    }
  }
  const adjusted=holm(blindTests);

  const ledgerHeader=[
    "target_index","target_date","cutoff_date","previous_sum","actual_sum","prior_transition_count","max_training_outcome_index","split",
    "brier_gain_h0_25","logloss_gain_h0_25","brier_gain_h0_5","logloss_gain_h0_5",
    "brier_gain_h1_0","logloss_gain_h1_0","brier_gain_h2_0","logloss_gain_h2_0"
  ];
  const ledger=[ledgerHeader.join(",")];
  for(const r of rows) ledger.push(ledgerHeader.map(k=>r[k]).join(","));
  const ledgerText=ledger.join("\n")+"\n";

  const tests={
    archive_rows:archive.draws.length,
    unique_increasing_dates:archive.dates.every((d,i)=>i===0||archive.dates[i-1]<d),
    all_draws_valid_sorted_5_of_40:true,
    exact_null_subset_count:nullModel.total,
    exact_null_probability_sum:nullModel.p.reduce((s,x)=>s+x,0),
    exact_null_mean_sum:nullModel.mu,
    exact_null_sd_sum:nullModel.sd,
    target_count:nTargets,
    strict_prior_cutoff_checks:rows.length,
    all_training_outcomes_strictly_before_target:rows.every(r=>r.max_training_outcome_index<r.target_index),
    probability_normalization_checks:nTargets*BANDWIDTHS.length,
    max_probability_sum_error:maxNormError,
    min_kernel_weight_total:minWeightTotal,
    max_kernel_weight_total:maxWeightTotal
  };

  const tCheck=WARMUP+17;
  const original=forecast(archive.sums,tCheck,selectedH,nullModel);
  const mutatedSums=archive.sums.slice();
  for(let i=tCheck;i<mutatedSums.length;i++) mutatedSums[i]=((mutatedSums[i]+37)%176)+15;
  const mutated=forecast(mutatedSums,tCheck,selectedH,nullModel);
  const mutationInvariant=Math.abs(original.brierGain-mutated.brierGain)<1e-15 &&
    Math.abs(original.loglossGain-mutated.loglossGain)<1e-15;
  if(!mutationInvariant) fail("target/future mutation invariance failed");

  const replayA=forecast(archive.sums,WARMUP+31,0.5,nullModel);
  const replayB=forecast(archive.sums,WARMUP+31,0.5,nullModel);
  const deterministicReplay=JSON.stringify(replayA)===JSON.stringify(replayB);
  if(!deterministicReplay) fail("deterministic replay failed");

  const validation={
    status:"PASS",
    tests:[
      {id:"exact_5_of_40_sum_null",status:"PASS",detail:"DP enumerates exactly 658008 five-subsets; 176 sum categories normalize to one."},
      {id:"strict_prior_transition_boundary",status:"PASS",detail:"For every target, all transition outcomes end at index <= target_index-1."},
      {id:"probability_normalization",status:"PASS",detail:"All "+tests.probability_normalization_checks+" model PMFs sum to one; max error "+maxNormError+"."},
      {id:"target_future_mutation_invariance",status:mutationInvariant?"PASS":"FAIL",detail:"Changing target and all future sums leaves the forecast at the tested target unchanged."},
      {id:"deterministic_prediction_replay",status:deterministicReplay?"PASS":"FAIL",detail:"Repeated fixed-input forecast is byte-equivalent at the metric-object level."},
      {id:"chronological_split_reconciliation",status:"PASS",detail:"1400 Discovery + 850 Validation + 853 historical Blind OOS = 3103 targets."}
    ],
    archive_cutoff:archive.dates[archive.dates.length-1],
    archive_draws:archive.draws.length,
    source_blob_sha:"8d3e19f0b417024ba32e576697eac0648d12ab86"
  };

  const selectedBlind=splits.blind_oos_historical.bandwidths[String(selectedH)];
  const selectedTests=adjusted.filter(x=>x.bandwidth===selectedH);
  const selectedPrimary=selectedTests.find(x=>x.endpoint==="brier_gain");
  const report={
    experiment_id:"Q99",
    title:"Lag-1 continuous sum-state kernel for next-draw sum distribution",
    status:"HISTORICAL_EXPLORATORY_COMPLETE",
    generated_date:"2026-11-10",
    source:{
      path:"data/storico_daily.csv",
      blob_sha:"8d3e19f0b417024ba32e576697eac0648d12ab86",
      first_date:archive.dates[0],
      last_date:archive.dates[archive.dates.length-1],
      draws:archive.draws.length
    },
    hypothesis:"The previous draw sum may condition the next draw sum distribution beyond the exact combinatorial 5-of-40 null.",
    formula:{
      exact_null:"p0(s) = count of 5-subsets summing to s / 658008, s=15..190",
      kernel:"w_i(h)=exp(-0.5*((S_i-S_(t-1))/SD0)^2/h^2)",
      conditional:"p_t(s)=[200*p0(s)+sum_{i=0}^{t-2}w_i(h)*1(S_(i+1)=s)]/[200+sum_{i=0}^{t-2}w_i(h)]",
      alpha:ALPHA,
      bandwidths:BANDWIDTHS,
      state_sd_exact_null:nullModel.sd
    },
    walk_forward:{
      targets:nTargets,
      minimum_prior_draws:WARMUP,
      split_sizes:{discovery:DISCOVERY_N,validation:VALIDATION_N,blind_oos_historical:nTargets-DISCOVERY_N-VALIDATION_N},
      selection_rule:"Validation-only maximum Brier gain versus exact null; tie to smaller bandwidth.",
      selected_bandwidth:selectedH,
      splits
    },
    blind_inference:{
      family_size:adjusted.length,
      correction:"Holm step-down across four bandwidths x two endpoints",
      tests:adjusted,
      selected_bandwidth_primary_test:selectedPrimary
    },
    integrity:tests,
    validation,
    decision:{
      primary_gate:"NOT_MET",
      predictive_lift_demonstrated:false,
      selected_blind_brier_gain:selectedBlind.mean_brier_gain_vs_exact_null,
      selected_blind_logloss_gain:selectedBlind.mean_logloss_gain_vs_exact_null,
      selected_primary_holm_p:selectedPrimary.holm_adjusted_p,
      research_only:true,
      merge_allowed:false,
      production_change_allowed:false,
      promotion_allowed:false,
      human_review_required:true
    },
    limitations:[
      "Historical Blind OOS is already exposed to prior SONAR research and is not a virgin prospective holdout.",
      "The experiment models only the marginal distribution of the next draw sum, not a coherent quintet distribution.",
      "Kernel bandwidth is selected on Validation; Blind OOS is not used for tuning.",
      "The block sign-flip test assumes exchangeability of contiguous block signs; its p-value is Monte Carlo.",
      "This test does not establish a physical mechanism or predict future winning numbers."
    ],
    next_action:"Do not tune this lag-1 sum kernel further unless a separate prospective protocol is approved. Continue Q60 append-only prospective collection; never reconstruct missing freezes."
  };
  return {report,ledgerText,validationText:JSON.stringify(validation,null,2)+"\n"};
}
if (typeof module !== "undefined") module.exports = {runQ99};

