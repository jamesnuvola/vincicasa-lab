from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.sonar_q141_q7_formula_adaptation import block_signflip_p,holm_adjust,select_formula_mask,split_sizes

def test_selector_uses_only_previous_window_and_ignores_current_outcome():
    ranks=np.full((106,1023),500000,dtype=np.int32)
    ranks[4:104,9]=100
    ranks[4:104,2]=200
    selected=select_formula_mask(ranks,104,100)
    assert selected==10
    altered=ranks.copy()
    altered[104:,:]=0
    assert select_formula_mask(altered,104,100)==selected

def test_selector_is_invariant_to_future_suffix():
    rng=np.random.default_rng(141)
    ranks=rng.integers(0,658008,size=(130,1023),dtype=np.int32)
    target=110
    selected=select_formula_mask(ranks,target,100)
    changed=ranks.copy()
    changed[target+1:,:]=rng.integers(0,658008,size=changed[target+1:,:].shape,dtype=np.int32)
    assert select_formula_mask(changed,target,100)==selected

def test_selector_rejects_insufficient_history():
    ranks=np.zeros((101,1023),dtype=np.int32)
    try:
        select_formula_mask(ranks,100,100)
    except ValueError:
        pass
    else:
        raise AssertionError("selector must require 100 strictly prior scored targets")

def test_split_counts_are_fixed():
    assert split_sizes(3286)==(1972,657,657)

def test_holm_adjustment_is_monotone_and_bounded():
    adjusted=holm_adjust([.01,.04,.03,.002])
    assert len(adjusted)==4
    assert all(0<=x<=1 for x in adjusted)
    assert adjusted[3]<=adjusted[0]<=adjusted[2]<=adjusted[1]

def test_block_signflip_is_deterministic():
    values=np.asarray([.2,.1,-.1,.3,.4,.1],dtype=np.float64)
    assert block_signflip_p(values,block_length=2,seed=141)==block_signflip_p(values,block_length=2,seed=141)
