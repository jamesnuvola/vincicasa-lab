import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np
import sonar_adaptive_novelty_rule_anticipation as q
from collections import Counter
def test_schema():
 assert len(q.NEW)==32 and len(q.NEW_FAMILIES)==32 and len(q.NAMES)==59 and len(set(q.NAMES))==59
 assert Counter(q.NEW_FAMILIES)==Counter({"ewma_hit_dynamics":7,"gap_dynamics":6,"cooccurrence_novelty":6,"rank_trajectory":5,"residual_surprise":2,"regime_transition_affinity":6})
def test_regime_bins_are_candidate_history_agnostic_and_well_defined():
 assert q.sum_regime_bin((1,2,3,4,5))==0
 assert q.sum_regime_bin((36,37,38,39,40))==4
 assert q.span_regime_bin((1,2,3,4,5))==0
 assert q.span_regime_bin((1,10,20,30,40))==3
 assert q.parity_entropy_bin((2,4,6,8,10))==0
 assert q.parity_entropy_bin((1,2,4,6,8))==1
 assert q.parity_entropy_bin((1,3,2,4,6))==2
 assert q.parity_entropy_bin((1,3,5,7,2))==1
 assert q.parity_entropy_bin((1,3,5,7,9))==0
def test_rank_tie_determinism():
 r=q.ranks(np.ones((40,2)));assert np.array_equal(r[:,0],np.arange(1,41))
def test_z_constant_finite(): assert np.isfinite(q.z(np.ones((40,3)))).all()

def test_rank_sum_accumulator_avoids_int16_overflow():
 ranks=np.array([40,40,40,40,40],dtype=np.int16)
 total=0
 for _ in range(1000): total+=q.rank_sum_int(ranks)
 assert isinstance(total,int) and total==200000

def test_rank_ties_and_near_ties_use_number_ascending():
 a=np.ones((40,2))
 a[1,0]=1.0+1e-13
 r=q.ranks(a)
 assert np.array_equal(r[:,1],np.arange(1,41))
 assert r[0,0]==1 and r[1,0]==2
 a[1,0]=1.0+1e-10
 r=q.ranks(a)
 assert r[1,0]==1 and r[0,0]==2
