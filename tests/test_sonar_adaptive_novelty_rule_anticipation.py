import numpy as np
import sonar_adaptive_novelty_rule_anticipation as q
def test_schema(): assert len(q.NEW)==32 and len(q.NAMES)==59 and len(set(q.NAMES))==59
def test_rank_tie_determinism():
 r=q.ranks(np.ones((40,2)));assert np.array_equal(r[:,0],np.arange(1,41))
def test_z_constant_finite(): assert np.isfinite(q.z(np.ones((40,3)))).all()
