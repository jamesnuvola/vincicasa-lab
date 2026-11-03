import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np
import sonar_adaptive_novelty_rule_anticipation as q
def test_schema(): assert len(q.NEW)==32 and len(q.NAMES)==59 and len(set(q.NAMES))==59
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
