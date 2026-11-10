#!/usr/bin/env python3
"""Discrete null calibration for Q92 number-hit share endpoints."""
from __future__ import annotations
from functools import lru_cache
import math
import operator
import numpy as np
POPULATION_SIZE=40
DRAW_SIZE=5
MIN_POSITIVE_FLOAT=float(np.nextafter(0.0,1.0))
def _integer(value,label,positive=False):
    if isinstance(value,(bool,np.bool_)): raise ValueError(label+" must be an integer, not bool")
    try: result=operator.index(value)
    except Exception as exc: raise ValueError(label+" must be an integer") from exc
    if positive and result<=0: raise ValueError(label+" must be positive")
    return int(result)
@lru_cache(maxsize=40)
def _single_target_pmf(top_k):
    top_k=_integer(top_k,"top_k",positive=True)
    if top_k>POPULATION_SIZE: raise ValueError("top_k outside 1..40")
    denominator=math.comb(POPULATION_SIZE,DRAW_SIZE)
    low=max(0,DRAW_SIZE-(POPULATION_SIZE-top_k)); high=min(DRAW_SIZE,top_k)
    probabilities=np.zeros(DRAW_SIZE+1,dtype=np.float64)
    for hits in range(low,high+1):
        probabilities[hits]=math.comb(top_k,hits)*math.comb(POPULATION_SIZE-top_k,DRAW_SIZE-hits)/denominator
    if abs(float(probabilities.sum())-1.0)>1e-14: raise RuntimeError("single-target Hypergeometric PMF normalization failed")
    return probabilities
@lru_cache(maxsize=32)
def _sum_upper_tail_table(targets,top_k):
    targets=_integer(targets,"targets",positive=True); top_k=_integer(top_k,"top_k",positive=True)
    base=_single_target_pmf(top_k); distribution=np.asarray([1.0],dtype=np.float64)
    for _ in range(targets): distribution=np.convolve(distribution,base)
    total=float(distribution.sum())
    if not math.isfinite(total) or abs(total-1.0)>5e-10: raise RuntimeError("summed Hypergeometric PMF normalization failed")
    distribution/=total
    tail=np.cumsum(distribution[::-1],dtype=np.float64)[::-1]
    np.maximum(tail,MIN_POSITIVE_FLOAT,out=tail); np.minimum(tail,1.0,out=tail)
    return tail
def exact_upper_tail_pvalue(successes,targets,top_k):
    """P(sum(X_t)>=successes), X_t iid Hypergeometric(40,top_k,5); float64 convolution."""
    successes=_integer(successes,"successes"); targets=_integer(targets,"targets",positive=True); top_k=_integer(top_k,"top_k",positive=True)
    if top_k>POPULATION_SIZE: raise ValueError("top_k outside 1..40")
    if successes<0 or successes>DRAW_SIZE*targets: raise ValueError("successes outside 0..5*targets")
    return float(_sum_upper_tail_table(targets,top_k)[successes])
def normal_approximation_upper_tail(successes,targets,top_k):
    """Continuity-corrected normal tail retained only for calibration audit."""
    successes=_integer(successes,"successes"); targets=_integer(targets,"targets",positive=True); top_k=_integer(top_k,"top_k",positive=True)
    if top_k>POPULATION_SIZE or successes<0 or successes>DRAW_SIZE*targets: raise ValueError("normal approximation arguments outside declared domain")
    probability=top_k/POPULATION_SIZE; mean=targets*DRAW_SIZE*probability
    variance=targets*DRAW_SIZE*probability*(1.0-probability)*(POPULATION_SIZE-DRAW_SIZE)/(POPULATION_SIZE-1.0)
    if variance<=0.0: return 1.0 if successes<=mean else 0.0
    z=(successes-0.5-mean)/math.sqrt(variance)
    return min(1.0,max(0.0,0.5*math.erfc(z/math.sqrt(2.0))))
