#!/usr/bin/env python3
"""Q84 Event-Level Strategy Atlas. Strict prior-only walk-forward; no promotion."""
from __future__ import annotations
import csv, hashlib, json, math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/sequence_agent"
FEATURES=["freq_5","freq_10","freq_20","freq_50","freq_100","freq_250","freq_500","freq_all","trend_5_vs_50","trend_10_vs_100","trend_20_vs_250","age_since_hit","gap_mean","gap_sd","overdue_ratio","position_log_frequency","pair_count_with_last_draw","neighbor_pm1_history","neighbor_pm2_history","lag_1","lag_2","lag_3","lag_5","lag_10","recent_3","recent_5","recent_10"]
ALPHA="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
MIN_HISTORY=50
SPLITS=("discovery","validation","blind_oos")

def normal_tail(z): return 0.5*math.erfc(z/math.sqrt(2))
def normal_two(z): return min(1.0,2*normal_tail(abs(z)))
def holm(pvalues):
    order=sorted(range(len(pvalues)),key=lambda i:(pvalues[i],i)); out=[1.0]*len(pvalues); run=0.0
    for rank,i in enumerate(order):
        run=max(run,min(1.0,(len(order)-rank)*pvalues[i]));out[i]=run
    return out
def binom_tail(n,p,k):
    if k<=0:return 1.0
    if k>n:return 0.0
    m=(1-p)**n;c=m
    for j in range(k-1):m*=((n-j)/(j+1))*p/(1-p);c+=m
    return max(0.0,min(1.0,1-c))
def hvar(k):
    q=k/40
    return 5*q*(1-q)*35/39
def git_blob_sha(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def encode_rank(r):return "".join(ALPHA[int(x)-1] for x in r)
def encode_actual(r,actual):return "".join(ALPHA[int(r[int(n)-1])-1] for n in actual)
def encode_numbers(nums):return "".join(ALPHA[int(n)-1] for n in nums)
def event_summary(indices):
    gaps=np.diff(indices).astype(int).tolist(); run=0; maxrun=0
    for j in range(len(indices)):
        run=run+1 if j and indices[j]==indices[j-1]+1 else 1;maxrun=max(maxrun,run)
    return {"event_count":int(len(indices)),"max_consecutive_events":int(maxrun),"recurrence_gap_mean_draws":float(np.mean(gaps)) if gaps else None,"recurrence_gap_median_draws":float(np.median(gaps)) if gaps else None,"recurrence_gap_min_draws":int(min(gaps)) if gaps else None,"recurrence_gap_max_draws":int(max(gaps)) if gaps else None}
def split_indices(T):
    ix=np.arange(T);return [ix[ix<T*.6],ix[(ix>=T*.6)&(ix<T*.8)],ix[ix>=T*.8]]
def rank_vector(scores):
    order=np.argsort(-scores,kind="stable")
    ranks=np.empty(40,dtype=np.int8);ranks[order]=np.arange(1,41,dtype=np.int8)
    return ranks
def rank_actual_pair(pair_scores,actual):
    # pair_scores: 40 x 351; exact rank with deterministic number tie-break.
    out=np.empty((5,pair_scores.shape[1]),dtype=np.int8)
    numbers=np.arange(40)[:,None]
    for j,n in enumerate(actual):
        v=pair_scores[int(n),:]
        out[j,:]=1+np.sum(pair_scores>v[None,:],axis=0)+np.sum((pair_scores==v[None,:])&(numbers<int(n)),axis=0)
    return out
def welch_p(high,low):
    if len(high)<2 or len(low)<2:return 1.0
    vh=np.var(high,ddof=1);vl=np.var(low,ddof=1);se=math.sqrt(vh/len(high)+vl/len(low))
    if se==0:return 1.0 if np.mean(high)==np.mean(low) else 0.0
    return normal_two((np.mean(high)-np.mean(low))/se)

def main():
    with ARCH.open(newline="",encoding="utf-8") as f:
        rows=list(csv.reader(f))
    dates=[r[0] for r in rows[1:]]
    draws=np.asarray([[int(x) for x in r[1:6]] for r in rows[1:]],dtype=np.int16)
    N=len(draws);T=N-MIN_HISTORY
    if T<=0:raise SystemExit("Q84 archive is too short")
    pairs=np.asarray([(a,b) for a in range(27) for b in range(a+1,27)],dtype=np.int16);P=len(pairs)
    prefix=np.zeros((N+1,40),dtype=np.int32);posprefix=np.zeros((N+1,5,40),dtype=np.int32)
    for i in range(N):
        prefix[i+1]=prefix[i];posprefix[i+1]=posprefix[i]
        for p in range(5):
            n=int(draws[i,p])-1;prefix[i+1,n]+=1;posprefix[i+1,p,n]+=1
    paircounts=np.zeros((40,40),dtype=np.int32);lastidx=[[] for _ in range(40)]
    gapsum=np.zeros(40);gapsq=np.zeros(40);gapn=np.zeros(40,dtype=np.int32)
    scores_all=np.zeros((T,40,27),dtype=np.float32);ranks_single=np.zeros((T,40,27),dtype=np.int8)
    actual_ranks_single=np.zeros((T,5,27),dtype=np.int8);hits_single=np.zeros((T,27,3),dtype=np.int8);rank_sum_single=np.zeros((T,27),dtype=np.int16);margin_single=np.zeros((T,27),dtype=np.float32)
    hits_pair=np.zeros((T,P,3),dtype=np.int8);rank_sum_pair=np.zeros((T,P),dtype=np.int16)
    union_hits=np.zeros((T,P),dtype=np.int8);union_size=np.zeros((T,P),dtype=np.int8);union_overlap=np.zeros((T,P),dtype=np.int8);union_lift=np.zeros((T,P),dtype=np.float32)
    split_ix=split_indices(T);counts=[len(x) for x in split_ix];split_of=np.empty(T,dtype=np.int8)
    for s,ix in enumerate(split_ix):split_of[ix]=s
    for t,i in enumerate(range(MIN_HISTORY,N)):
        raw=np.zeros((40,27),dtype=np.float64)
        for c,w in enumerate((5,10,20,50,100,250,500)):
            st=max(0,i-w);raw[:,c]=prefix[i]-prefix[st]
        raw[:,7]=prefix[i]
        raw[:,8]=raw[:,0]/max(1,min(i,5))-raw[:,3]/max(1,min(i,50))
        raw[:,9]=raw[:,1]/max(1,min(i,10))-raw[:,4]/max(1,min(i,100))
        raw[:,10]=raw[:,2]/max(1,min(i,20))-raw[:,5]/max(1,min(i,250))
        for n in range(40):
            raw[n,11]=i-lastidx[n][-1] if lastidx[n] else i+1
            raw[n,12]=gapsum[n]/gapn[n] if gapn[n] else max(1,i)
            raw[n,13]=math.sqrt(max(0,gapsq[n]/gapn[n]-(gapsum[n]/gapn[n])**2)) if gapn[n] else 0
            raw[n,14]=raw[n,11]/max(raw[n,12],1)
            raw[n,17]=sum(prefix[i,q] for q in range(max(0,n-1),min(40,n+2)) if q!=n)
            raw[n,18]=sum(prefix[i,q] for q in range(max(0,n-2),min(40,n+3)) if q!=n)
            for lag,col in ((1,19),(2,20),(3,21),(5,22),(10,23)):raw[n,col]=int(i>=lag and n+1 in draws[i-lag])
            for w,col in ((3,24),(5,25),(10,26)):raw[n,col]=prefix[i,n]-prefix[max(0,i-w),n]
        raw[:,15]=np.log((posprefix[i]+.5)/(i+20)).mean(axis=0)
        raw[:,16]=paircounts[:,draws[i-1]-1].sum(axis=1)/5
        mu=raw.mean(axis=0);sd=raw.std(axis=0);sd[sd<1e-12]=1
        z=((raw-mu)/sd).astype(np.float32);scores_all[t]=z
        order=np.argsort(-z,axis=0,kind="stable")
        rv=np.empty((40,27),dtype=np.int8)
        rv[order,np.arange(27)]=np.arange(1,41,dtype=np.int8)[:,None]
        ranks_single[t]=rv
        margin_single[t]=z[order[4],np.arange(27)]-z[order[5],np.arange(27)]
        actual=draws[i]-1;ar=rv[actual,:];actual_ranks_single[t]=ar
        hits_single[t,:,0]=(ar<=5).sum(axis=0);hits_single[t,:,1]=(ar<=10).sum(axis=0);hits_single[t,:,2]=(ar<=20).sum(axis=0);rank_sum_single[t]=ar.sum(axis=0)
        ps=(z[:,pairs[:,0]]+z[:,pairs[:,1]])/2
        apr=rank_actual_pair(ps,actual)
        hits_pair[t,:,0]=(apr<=5).sum(axis=0);hits_pair[t,:,1]=(apr<=10).sum(axis=0);hits_pair[t,:,2]=(apr<=20).sum(axis=0);rank_sum_pair[t]=apr.sum(axis=0)
        top5=rv<=5
        ov=(top5[:,pairs[:,0]]&top5[:,pairs[:,1]]).sum(axis=0)
        sz=10-ov
        uh=((ar[:,pairs[:,0]]<=5)|(ar[:,pairs[:,1]]<=5)).sum(axis=0)
        ex=5*sz/40
        union_overlap[t]=ov;union_size[t]=sz;union_hits[t]=uh;union_lift[t]=uh-ex
        for a in range(5):
            for b in range(a+1,5):
                x=int(draws[i,a])-1;y=int(draws[i,b])-1;paircounts[x,y]+=1;paircounts[y,x]+=1
        for n in draws[i]:
            v=int(n)-1
            if lastidx[v]:
                g=i-lastidx[v][-1];gapsum[v]+=g;gapsq[v]+=g*g;gapn[v]+=1
            lastidx[v].append(i)
    # Pair comparator is selected on discovery, then frozen before validation/blind.
    best_component=np.zeros(P,dtype=np.int8)
    for p,(a,b) in enumerate(pairs):
        ma=hits_single[split_ix[0],a,0].mean();mb=hits_single[split_ix[0],b,0].mean()
        ra=rank_sum_single[split_ix[0],a].mean();rb=rank_sum_single[split_ix[0],b].mean()
        best_component[p]=a if ma>mb or (ma==mb and (ra<rb or (ra==rb and a<b))) else b
    gain_pair=hits_pair[:,:,0]-hits_single[:,best_component,0]
    # Fixed family-wide tests.
    baseline_all5=1/math.comb(40,5);perf_tests=[];perf_keys=[]
    for c in range(27+P):
        for s,ix in enumerate(split_ix):
            n=len(ix);h5=hits_single[ix,c,0].sum() if c<27 else hits_pair[ix,c-27,0].sum()
            h10=hits_single[ix,c,1].sum() if c<27 else hits_pair[ix,c-27,1].sum()
            h20=hits_single[ix,c,2].sum() if c<27 else hits_pair[ix,c-27,2].sum()
            hAll=(hits_single[ix,c,0]==5).sum() if c<27 else (hits_pair[ix,c-27,0]==5).sum()
            for e,k,h in (("top5",5,h5),("top10",10,h10),("top20",20,h20)):
                z=(h-n*5*k/40-.5)/math.sqrt(max(1e-12,n*hvar(k)));perf_tests.append(normal_tail(z));perf_keys.append((c,s,e))
            perf_tests.append(binom_tail(n,baseline_all5,int(hAll)));perf_keys.append((c,s,"all5"))
    perf_adj=holm(perf_tests);perf_map={(k):{"p_raw":float(p),"p_holm":float(a)} for k,p,a in zip(perf_keys,perf_tests,perf_adj)}
    union_tests=[];union_keys=[];gain_tests=[];gain_keys=[]
    for p in range(P):
        for s,ix in enumerate(split_ix):
            ul=union_lift[ix,p].sum();uv=sum(hvar(int(k)) for k in union_size[ix,p])
            union_tests.append(normal_tail((ul-.5)/math.sqrt(max(1e-12,uv))));union_keys.append((p,s))
            g=gain_pair[ix,p].astype(float);sd=g.std(ddof=1) if len(g)>1 else 0
            gain_tests.append(normal_two(g.mean()/(sd/math.sqrt(len(g))) if sd else (0 if g.mean()==0 else math.copysign(math.inf,g.mean()))));gain_keys.append((p,s))
    uadj=holm(union_tests);gadj=holm(gain_tests)
    umap={k:{"p_raw":float(p),"p_holm":float(a)} for k,p,a in zip(union_keys,union_tests,uadj)}
    gmap={k:{"p_raw":float(p),"p_holm":float(a)} for k,p,a in zip(gain_keys,gain_tests,gadj)}
    selected_union=sorted(range(P),key=lambda p:(-union_lift[split_ix[0],p].mean(),p))[:12]
    selected_pair=sorted(range(P),key=lambda p:(gain_pair[split_ix[0],p].mean(),p))[:12]
    # Selected full-rank ledger: 27 singles, 12 union-minrank permutations, 12 equal-weight pair composites.
    selected_defs=[("single",c,(c,)) for c in range(27)]+[("union",p,tuple(pairs[p])) for p in selected_union]+[("pair",p,tuple(pairs[p])) for p in selected_pair]
    S=len(selected_defs);sel_ranks=np.zeros((T,S,40),dtype=np.int8);sel_margin=np.zeros((T,S),dtype=np.float32);sel_outcome=np.zeros((T,S),dtype=np.float32)
    for t in range(T):
        for c in range(27):sel_ranks[t,c]=ranks_single[t,:,c];sel_margin[t,c]=margin_single[t,c];sel_outcome[t,c]=hits_single[t,c,0]
        for q,p in enumerate(selected_union):
            a,b=pairs[p];s=27+q;minrank=np.minimum(ranks_single[t,:,a],ranks_single[t,:,b]);order=np.argsort(minrank,kind="stable");rv=np.empty(40,dtype=np.int8);rv[order]=np.arange(1,41,dtype=np.int8);sel_ranks[t,s]=rv;sel_margin[t,s]=min(margin_single[t,a],margin_single[t,b]);sel_outcome[t,s]=union_lift[t,p]
        for q,p in enumerate(selected_pair):
            a,b=pairs[p];s=39+q;score=(scores_all[t,:,a]+scores_all[t,:,b])/2;rv=rank_vector(score);sel_ranks[t,s]=rv;order=np.argsort(-score,kind="stable");sel_margin[t,s]=score[order[4]]-score[order[5]];sel_outcome[t,s]=hits_pair[t,p,0]
    thresholds=np.quantile(sel_margin[split_ix[0]],.75,axis=0)
    cond_tests=[];cond_keys=[];cond_stats={}
    for s in range(S):
        for z,ix in enumerate(split_ix):
            hi=sel_margin[ix,s]>=thresholds[s];yh=sel_outcome[ix,s][hi];yl=sel_outcome[ix,s][~hi];p=welch_p(yh,yl);cond_tests.append(p);cond_keys.append((s,z));cond_stats[(s,z)]={"q75_discovery_margin":float(thresholds[s]),"high_count":int(len(yh)),"low_count":int(len(yl)),"mean_high":float(yh.mean()) if len(yh) else 0,"mean_low":float(yl.mean()) if len(yl) else 0,"delta_high_minus_low":float(yh.mean()-yl.mean()) if len(yh) and len(yl) else 0,"p_raw":float(p)}
    cadj=holm(cond_tests)
    for k,p,a in zip(cond_keys,cond_tests,cadj):cond_stats[k]["p_holm"]=float(a)
    # Moving-block bootstrap on discovery-selected candidates, validation and blind only.
    rng=np.random.default_rng(20261109);boot_tests=[];boot_keys=[];boot_results={}
    def boot_mean(series,ix,reps=500,block=10):
        n=len(ix);blocks=math.ceil(n/block);out=np.empty(reps)
        for r in range(reps):
            starts=rng.integers(0,n,size=blocks);sample=[]
            for st in starts:
                sample.extend(ix[(st+np.arange(block))%n].tolist())
                if len(sample)>=n:break
            out[r]=np.mean(series[np.asarray(sample[:n])])
        return out
    for fam,sel,series in (("union",selected_union,union_lift),("pair",selected_pair,gain_pair)):
        for p in sel:
            for z in (1,2):
                ix=split_ix[z];v=boot_mean(series[:,p],ix);lo,hi=np.quantile(v,[.025,.975]);le=np.sum(v<=0);ge=np.sum(v>=0);pb=min(1,2*min((le+1)/(len(v)+1),(ge+1)/(len(v)+1)));k=(fam,p,z)
                boot_tests.append(float(pb));boot_keys.append(k);boot_results[k]={"reps":500,"block_length_draws":10,"ci95_low":float(lo),"ci95_high":float(hi),"p_bootstrap_raw":float(pb)}
    badj=holm(boot_tests)
    for k,p,a in zip(boot_keys,boot_tests,badj):boot_results[k]["p_bootstrap_holm"]=float(a)
    # Ranking-flow metrics for selected strategies.
    flow=[]
    for s in range(S):
        vel=[];turn=[];jac=[]
        for t in range(1,T):
            a=sel_ranks[t-1,s];b=sel_ranks[t,s];ov=int(np.sum((a<=5)&(b<=5)));vel.append(np.abs(a-b).mean()/(39));turn.append(5-ov);jac.append(ov/(10-ov))
        flow.append({"transitions":T-1,"mean_normalized_rank_velocity":float(np.mean(vel)),"mean_top5_turnover":float(np.mean(turn)),"mean_top5_jaccard":float(np.mean(jac))})
    flow_summary={}
    for fam,sl in (("single",slice(0,27)),("union",slice(27,39)),("composite",slice(39,51))):
        f=flow[sl];flow_summary[fam]={"selected_strategies":len(f),"mean_normalized_rank_velocity":float(np.mean([x["mean_normalized_rank_velocity"] for x in f])),"mean_top5_turnover":float(np.mean([x["mean_top5_turnover"] for x in f])),"mean_top5_jaccard":float(np.mean([x["mean_top5_jaccard"] for x in f]))}
    # Event recurrence for the 729 ex-ante strategies.
    catalog=[];life=[]
    def events(series):
        ev=np.flatnonzero(series>0);perfect=np.flatnonzero(series==5);return ev,perfect,event_summary(ev)
    def perf_metric(c,z):
        ix=split_ix[z];n=len(ix);h=[]
        for k in (5,10,20):h.append(int((hits_single[ix,c,k//10] if c<27 else hits_pair[ix,c-27,k//10]).sum()) if False else 0)
        if c<27:arr=hits_single[ix,c,:];rank=rank_sum_single[ix,c]
        else:arr=hits_pair[ix,c-27,:];rank=rank_sum_pair[ix,c-27]
        h5=int(arr[:,0].sum());h10=int(arr[:,1].sum());h20=int(arr[:,2].sum());all5=int(np.sum(arr[:,0]==5))
        out={"targets":n,"top5_number_hits_total":h5,"mean_hits_top5":h5/n,"baseline_mean_hits_top5":.625,"lift_top5":h5/n-.625,"top10_number_hits_total":h10,"mean_hits_top10":h10/n,"baseline_mean_hits_top10":1.25,"lift_top10":h10/n-1.25,"top20_number_hits_total":h20,"mean_hits_top20":h20/n,"baseline_mean_hits_top20":2.5,"lift_top20":h20/n-2.5,"mean_rank_sum":float(rank.mean()),"all5_top5_count":all5,"all5_top5_expected":n*baseline_all5}
        endpoint={"top5":"top5_number_hits","top10":"top10_number_hits","top20":"top20_number_hits","all5":"all5"}
        for e,ep in endpoint.items():
            m=perf_map[(c,z,ep)];out[e+"_p_raw"]=m["p_raw"];out[e+"_p_holm"]=m["p_holm"]
        return out
    def union_metric(p,z):
        ix=split_ix[z];n=len(ix);h=int(union_hits[ix,p].sum());ex=float((5*union_size[ix,p]/40).sum());l=float(union_lift[ix,p].sum());v=float(sum(hvar(int(k)) for k in union_size[ix,p]));m=umap[(p,z)]
        return {"targets":n,"mean_union_size":float(union_size[ix,p].mean()),"mean_component_top5_overlap":float(union_overlap[ix,p].mean()),"mean_actual_union_hits":h/n,"mean_expected_union_hits":ex/n,"mean_lift_conditional_hypergeom":l/n,"z_conditional_hypergeom":(l-.5)/math.sqrt(max(v,1e-12)),"p_raw":m["p_raw"],"p_holm":m["p_holm"],"all5_union_count":int(np.sum(union_hits[ix,p]==5))}
    def gain_metric(p,z):
        ix=split_ix[z];g=gain_pair[ix,p].astype(float);m=gmap[(p,z)];return {"targets":len(ix),"selected_component_feature":FEATURES[int(best_component[p])],"mean_gain_vs_discovery_selected_component":float(g.mean()),"gain_sd":float(g.std(ddof=1)),"gain_p_raw":m["p_raw"],"gain_p_holm":m["p_holm"]}
    def condition_for(s):return [{ "split":SPLITS[z],**cond_stats[(s,z)]} for z in range(3)]
    selectedU=set(selected_union);selectedP=set(selected_pair)
    def classify(fam,evcount,perfect,blind,disc,sel,p):
        c=[]
        if perfect==1:c.append("ONE_TARGET_ALL5")
        if evcount>1:c.append("INTERMITTENT")
        if sel and cond_stats[(sel,0)]["delta_high_minus_low"]>0 and cond_stats[(sel,0)]["p_holm"]<.05:c.append("CONDITIONAL_STATE_DISCOVERY")
        if fam=="union":
            if disc["mean_lift_conditional_hypergeom"]>0 and disc["p_holm"]<.05:c.append("COMPLEMENTARY_DISCOVERY_ONLY")
            if disc["mean_component_top5_overlap"]>=4:c.append("REDUNDANT_COMPONENT_TOP5")
            if sel is not None and boot_results[("union",p,2)]["p_bootstrap_holm"]>=.05:c.append("BLOCK_BOOTSTRAP_NOT_CONFIRMED")
            if blind["p_holm"]>=.05 and "COMPLEMENTARY_DISCOVERY_ONLY" not in c:c.append("NULL_OR_UNSTABLE")
        elif fam=="pair":
            if disc["mean_gain_vs_discovery_selected_component"]>0 and disc["gain_p_holm"]<.05:c.append("COMPLEMENTARY_ANALYTIC_DISCOVERY_ONLY")
            if disc["mean_gain_vs_discovery_selected_component"]<0 and disc["gain_p_holm"]<.05:c.append("ANTAGONISTIC_DIRECTIONAL_DISCOVERY_ONLY")
            if sel is not None and boot_results[("pair",p,2)]["p_bootstrap_holm"]>=.05:c.append("BLOCK_BOOTSTRAP_NOT_CONFIRMED")
            if blind["top5_p_holm"]>=.05 and not any(x.startswith(("COMPLEMENTARY","ANTAGONISTIC")) for x in c):c.append("NULL_OR_UNSTABLE")
        else:
            if blind["top5_p_holm"]>=.05 and "CONDITIONAL_STATE_DISCOVERY" not in c:c.append("NULL_OR_UNSTABLE")
        return c or ["EXPLORATORY_NO_ADJUSTED_SIGNAL"]
    for c in range(27):
        ev,perfect,es=events(hits_single[:,c,0]);metrics=[perf_metric(c,z) for z in range(3)];sel=c
        catalog.append({"strategy_id":f"Q84-S-{c:02d}","formula_id":f"Q80-P1-{c:02d}","family":"SINGLE_FEATURE","feature_indices":[c],"formula_features":[FEATURES[c]],"ex_ante":True,"retrospective_only":False,"selected_for_full_target_ledger":True,"score_definition":"Per-target z-scored single feature; descending rank, stable number tie-break.","classifications":classify("single",len(ev),len(perfect),metrics[2],None,sel,None),"event_count_any_top5":es["event_count"],"all5_top5_count":len(perfect),"event_lifecycle":es,"event_dates_top5_any_hit":[dates[int(t)+MIN_HISTORY] for t in ev],"all5_top5_dates":[dates[int(t)+MIN_HISTORY] for t in perfect],"split_metrics":dict(zip(SPLITS,metrics)),"condition_state":condition_for(sel),"flow_metrics":flow[sel]})
    for p,(a,b) in enumerate(pairs):
        ue,up,us=events(union_hits[:,p]);pe,pp,ps=events(hits_pair[:,p,0]);umets=[union_metric(p,z) for z in range(3)];pmets=[gain_metric(p,z) for z in range(3)];ui=27+selected_union.index(p) if p in selectedU else None;pi=39+selected_pair.index(p) if p in selectedP else None
        catalog.append({"strategy_id":f"Q84-U-{a:02d}_{b:02d}","formula_id":f"Q84-U5-{a:02d}_{b:02d}","family":"UNION_OF_SINGLE_TOP5","feature_indices":[int(a),int(b)],"formula_features":[FEATURES[a],FEATURES[b]],"ex_ante":True,"retrospective_only":False,"selected_for_full_target_ledger":p in selectedU,"score_definition":"Union of component Top5 candidate sets; variable size tested against target-wise hypergeometric null.","classifications":classify("union",len(ue),len(up),umets[2],umets[0],ui,p),"event_count_any_top5":us["event_count"],"all5_top5_count":len(up),"event_lifecycle":us,"event_dates_top5_any_hit":[dates[int(t)+MIN_HISTORY] for t in ue] if p in selectedU else [],"all5_top5_dates":[dates[int(t)+MIN_HISTORY] for t in up] if p in selectedU else [],"split_metrics":dict(zip(SPLITS,umets)),"condition_state":condition_for(ui) if ui is not None else None,"flow_metrics":flow[ui] if ui is not None else None})
        catalog.append({"strategy_id":f"Q84-P-{a:02d}_{b:02d}","formula_id":f"Q80-P2-{a:02d}_{b:02d}","family":"EQUAL_WEIGHT_PAIR_COMPOSITE","feature_indices":[int(a),int(b)],"formula_features":[FEATURES[a],FEATURES[b]],"ex_ante":True,"retrospective_only":False,"selected_for_full_target_ledger":p in selectedP,"score_definition":"Mean of two per-target z-scored features; stable descending rank.","gain_comparator_feature":FEATURES[int(best_component[p])],"gain_comparator_frozen_on_discovery":True,"classifications":classify("pair",len(pe),len(pp),pmets[2],pmets[0],pi,p),"event_count_any_top5":ps["event_count"],"all5_top5_count":len(pp),"event_lifecycle":ps,"event_dates_top5_any_hit":[dates[int(t)+MIN_HISTORY] for t in pe] if p in selectedP else [],"all5_top5_dates":[dates[int(t)+MIN_HISTORY] for t in pp] if p in selectedP else [],"split_metrics":dict(zip(SPLITS,pmets)),"condition_state":condition_for(pi) if pi is not None else None,"flow_metrics":flow[pi] if pi is not None else None})
    # Retrospective best-per-target is explicitly descriptive and outcome-selected.
    best_id=np.empty(T,dtype=np.int16)
    for t in range(T):
        keys=np.concatenate([rank_sum_single[t,:,None],hits_single[t,:,2,None],-hits_single[t,:,0,None]],axis=1)
        kp=np.concatenate([rank_sum_pair[t,:,None],hits_pair[t,:,2,None],-hits_pair[t,:,0,None]],axis=1)
        ix=np.lexsort((keys[:,2],keys[:,1],keys[:,0]));ip=np.lexsort((kp[:,2],kp[:,1],kp[:,0]))
        best_id[t]=int(ix[0]) if tuple(keys[ix[0]])<=tuple(kp[ip[0]]) else 27+int(ip[0])
    retro_metrics={}
    for z,ix in enumerate(split_ix):
        h5=[];h10=[];h20=[];rs=[]
        for t in ix:
            b=int(best_id[t])
            if b<27:h5.append(int(hits_single[t,b,0]));h10.append(int(hits_single[t,b,1]));h20.append(int(hits_single[t,b,2]));rs.append(int(rank_sum_single[t,b]))
            else:b-=27;h5.append(int(hits_pair[t,b,0]));h10.append(int(hits_pair[t,b,1]));h20.append(int(hits_pair[t,b,2]));rs.append(int(rank_sum_pair[t,b]))
        retro_metrics[SPLITS[z]]={"targets":len(ix),"mean_rank_sum":float(np.mean(rs)),"mean_hits_top5":float(np.mean(h5)),"mean_hits_top10":float(np.mean(h10)),"mean_hits_top20":float(np.mean(h20)),"all5_top5_count":int(np.sum(np.asarray(h5)==5))}
    catalog.append({"strategy_id":"Q84-RETRO-BEST-PER-TARGET","formula_id":"RETROSPECTIVE_MAX_OVER_378","family":"RETROSPECTIVE_META_STRATEGY","ex_ante":False,"retrospective_only":True,"score_definition":"Per target, outcome-selected minimum rank sum among 27 singles+351 pair composites; descriptive only.","classifications":["RETROSPECTIVE","NOT_EX_ANTE","DESCRIPTIVE_UPPER_BOUND"],"split_metrics":retro_metrics})
    # Full rank ledger, with compact bijective rank encoding (1..40 -> A..n).
    header=["target_date","cutoff_date","prior_draws","actual_quintet","split","retrospective_best_strategy_id","retrospective_best_formula_id","retrospective_best_rank_sum","retrospective_best_hits_top5","retrospective_best_hits_top20","retrospective_status"]
    for c in range(27):header += [f"rank_vector_Q84-S-{c:02d}",f"actual_ranks_Q84-S-{c:02d}"]
    for q,p in enumerate(selected_union):header += [f"rank_vector_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"actual_ranks_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"candidate_union_numbers_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"candidate_union_size_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"candidate_union_actual_hits_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"candidate_union_expected_hits_Q84-U-{pairs[p,0]:02d}_{pairs[p,1]:02d}"]
    for q,p in enumerate(selected_pair):header += [f"rank_vector_Q84-P-{pairs[p,0]:02d}_{pairs[p,1]:02d}",f"actual_ranks_Q84-P-{pairs[p,0]:02d}_{pairs[p,1]:02d}"]
    ledger=OUT/"strategy_atlas_target_ledger.csv";ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(header)
        for t in range(T):
            i=t+MIN_HISTORY;act=draws[i];bi=int(best_id[t]);bId=f"Q84-S-{bi:02d}" if bi<27 else f"Q84-P-{pairs[bi-27,0]:02d}_{pairs[bi-27,1]:02d}";bF=f"Q80-P1-{bi:02d}" if bi<27 else f"Q80-P2-{pairs[bi-27,0]:02d}_{pairs[bi-27,1]:02d}"
            if bi<27:br=rank_sum_single[t,bi];bh5=hits_single[t,bi,0];bh20=hits_single[t,bi,2]
            else:br=rank_sum_pair[t,bi-27];bh5=hits_pair[t,bi-27,0];bh20=hits_pair[t,bi-27,2]
            row=[dates[i],dates[i-1],i," ".join(map(str,act)),SPLITS[int(split_of[t])],bId,bF,int(br),int(bh5),int(bh20),"RETROSPECTIVE_ONLY"]
            for c in range(27):row += [encode_rank(ranks_single[t,:,c]),encode_actual(ranks_single[t,:,c],act)]
            for q,p in enumerate(selected_union):
                a,b=pairs[p];rv=sel_ranks[t,27+q];nums=np.flatnonzero((ranks_single[t,:,a]<=5)|(ranks_single[t,:,b]<=5))+1
                row += [encode_rank(rv),encode_actual(rv,act),encode_numbers(nums),int(union_size[t,p]),int(union_hits[t,p]),float(5*union_size[t,p]/40)]
            for q,p in enumerate(selected_pair):row += [encode_rank(sel_ranks[t,39+q]),encode_actual(sel_ranks[t,39+q],act)]
            w.writerow(row)
    catalog_path=OUT/"strategy_atlas_catalog.jsonl";catalog_path.write_text("".join(json.dumps(x,separators=(",",":"),ensure_ascii=True)+"\n" for x in catalog),encoding="utf-8")
    lifecycle={"schema_version":"1.0","task_id":"Q84","status":"EXPLORATORY_COMPLETE_PENDING_HUMAN_REVIEW","review_status":"PENDING_HUMAN_REVIEW","source_archive":"data/storico_daily.csv","source_archive_blob_sha":git_blob_sha(ARCH.read_bytes()),"draw_count":N,"first_date":dates[0],"last_date":dates[-1],"minimum_prior_history":MIN_HISTORY,"target_count":T,"split_counts":dict(zip(SPLITS,counts)),"strategy_count":len(catalog),"ex_ante_strategy_count":729,"retrospective_meta_strategy_count":1,"strategies":[{k:r.get(k) for k in ("strategy_id","family","formula_id","feature_indices","formula_features","selected_for_full_target_ledger","event_count_any_top5","all5_top5_count","event_lifecycle","classifications","condition_state","flow_metrics")} for r in catalog]}
    life_path=OUT/"strategy_atlas_lifecycle.json";life_path.write_text(json.dumps(lifecycle,separators=(",",":")),encoding="utf-8")
    # Report family significance and compact measured summaries.
    perf_sig={SPLITS[z]:{e:sum(1 for k,m in perf_map.items() if k[1]==z and k[2]==e and m["p_holm"]<.05) for e in ("top5_number_hits","top10_number_hits","top20_number_hits","all5")} for z in range(3)}
    union_sig={SPLITS[z]:sum(1 for (p,s),m in umap.items() if s==z and m["p_holm"]<.05) for z in range(3)}
    gain_sig={SPLITS[z]:sum(1 for (p,s),m in gmap.items() if s==z and m["p_holm"]<.05) for z in range(3)}
    cond_sig={SPLITS[z]:sum(1 for (s,sp),m in cond_stats.items() if sp==z and m["p_holm"]<.05) for z in range(3)}
    top_single_blind=sorted([{"feature":FEATURES[c],"mean_hits_top5":float(hits_single[split_ix[2],c,0].mean()),"lift_top5":float(hits_single[split_ix[2],c,0].mean()-.625),"p_raw":perf_map[(c,2,"top5_number_hits")]["p_raw"],"p_holm":perf_map[(c,2,"top5_number_hits")]["p_holm"]} for c in range(27)],key=lambda x:-x["lift_top5"])[:5]
    top_union=[{"pair":[FEATURES[int(pairs[p,0])],FEATURES[int(pairs[p,1])]],"discovery":union_metric(p,0),"validation":union_metric(p,1),"blind_oos":union_metric(p,2),"bootstrap_blind":boot_results[("union",p,2)]} for p in selected_union[:5]]
    top_gain=[{"pair":[FEATURES[int(pairs[p,0])],FEATURES[int(pairs[p,1])]],"selected_component":FEATURES[int(best_component[p])],"discovery":gain_metric(p,0),"validation":gain_metric(p,1),"blind_oos":gain_metric(p,2),"bootstrap_blind":boot_results[("pair",p,2)]} for p in selected_pair[:5]]
    report={"schema_version":"1.0","task_id":"Q84","status":"EXPLORATORY_COMPLETE_PENDING_HUMAN_REVIEW","review_status":"PENDING_HUMAN_REVIEW","generated_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"source_archive":"data/storico_daily.csv","source_archive_blob_sha":git_blob_sha(ARCH.read_bytes()),"archive":{"draw_count":N,"first_date":dates[0],"last_date":dates[-1],"eligible_target_count":T,"minimum_prior_history":MIN_HISTORY},"split_counts":dict(zip(SPLITS,counts)),"finite_grammar":{"single_features":27,"equal_weight_pairs":351,"top5_unions":351,"ex_ante_strategy_definitions":729,"retrospective_meta_strategy_definitions":1,"catalog_records":len(catalog),"full_rank_ledger_strategies":51,"full_rank_ledger_rows":T},"multiple_testing":{"performance_family_tests":len(perf_tests),"performance_holm_significant_by_split":perf_sig,"pair_union_conditional_hypergeometric_tests":len(uTests) if False else len(union_tests),"pair_union_holm_significant_by_split":union_sig,"pair_gain_analytic_normal_tests":len(gain_tests),"pair_gain_analytic_normal_holm_significant_by_split":gain_sig,"conditional_state_tests":len(cond_tests),"conditional_state_holm_significant_by_split":cond_sig,"selected_pair_block_bootstrap_tests":len(boot_tests),"selected_pair_bootstrap_holm_significant":sum(a<.05 for a in badj),"bootstrap_replicates":500,"bootstrap_block_length_draws":10,"gain_comparator":"Best component feature selected on discovery mean Top5 hits (tie: mean rank sum, then feature index), frozen before validation/blind.","bootstrap_holm_family":"24 discovery-selected union/pair candidates × validation/blind (48 tests)."},"baseline":{"top5_mean_hits":.625,"top10_mean_hits":1.25,"top20_mean_hits":2.5,"mean_rank_per_actual_number":20.5,"mean_rank_sum_five":102.5,"all5_top5_probability":baseline_all5,"all5_top5_expected_per_1000":1000*baseline_all5},"measured":{"top5_single_features_blind_oos":top_single_blind,"top5_union_pairs_discovery_selected":top_union,"pair_gain_candidates_discovery_selected":top_gain,"retrospective_best_per_target":retro_metrics,"flow_summary":flow_summary},"flow_definition":{"normalized_rank_velocity":"Mean absolute rank displacement over 40 numbers between consecutive rankings divided by 40×39.","top5_turnover":"5 minus overlap of consecutive ranking Top5 sets.","top5_jaccard":"Top5 intersection / Top5 union.","state_intensity":"Rank5-score minus rank6-score; q75 threshold fitted on discovery only."},"artifact_checksums":{},"limitations":["Fixed-rule historical walk-forward uses only prior rows for features/rankings, but rules were not prospectively frozen at the time.","Finite grammar: 27 features, 351 equal-weight pairs and 351 Top5 unions; other nonlinear, conditional and weighted families remain open.","Pair gain comparator is selected on discovery and frozen before validation/blind; analytic p-values may understate serial dependence. Selected candidates receive block bootstrap and Holm across 48 tests.","Conditional q75 thresholds use discovery only; Welch-normal p-values Holm-corrected across 153 tests.","Retrospective best-per-target selects using outcomes and is descriptive only.","Q84 is not a promotion gate; separate Q60 policy requires 200 paired shadow targets."],"next_action":"Human review of Q84 atlas; continue append-only prospective shadow collection; no automatic promotion."}
    report_path=OUT/"strategy_atlas_report.json"
    # checksum payloads before report.
    report["artifact_checksums"]={"strategy_atlas_catalog_jsonl":git_blob_sha(catalog_path.read_bytes()),"strategy_atlas_target_ledger_csv":git_blob_sha(ledger.read_bytes()),"strategy_atlas_lifecycle_json":git_blob_sha(life_path.read_bytes())}
    report_path.write_text(json.dumps(report,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"status":report["status"],"draw_count":N,"target_count":T,"split_counts":counts,"catalog_records":len(catalog),"ledger_rows":T,"ledger_columns":len(header),"performance_tests":len(perf_tests),"union_tests":len(union_tests),"gain_tests":len(gain_tests),"conditional_tests":len(cond_tests),"bootstrap_tests":len(boot_tests),"holm_significant":{"performance":perf_sig,"union":union_sig,"gain_analytic":gain_sig,"conditional":cond_sig,"bootstrap":sum(a<.05 for a in badj)},"top_blind_single":top_single_blind,"top_union":top_union,"top_gain":top_gain,"flow":flow_summary,"artifact_checksums":report["artifact_checksums"]},separators=(",",":")))

if __name__=="__main__":main()
