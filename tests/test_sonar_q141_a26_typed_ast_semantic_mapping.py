import unittest, math
import numpy as np
from scripts.sonar_q141_a26_typed_ast_semantic_mapping import (
 Q7_MAP,Q90_MAP,QLIN,QNON,QALL,SHARED,refs,mask,op_type,group_state,holm,canon,sha,strict_prior_window
)

class A26Tests(unittest.TestCase):
 def test_q7_ten_families(self): self.assertEqual(len(Q7_MAP),10)
 def test_q90_twenty_features(self): self.assertEqual(len(Q90_MAP),20)
 def test_five_shared_concepts(self): self.assertEqual(len(SHARED),5)
 def test_operator_partition(self):
  self.assertEqual(len(QLIN),5);self.assertEqual(len(QNON),2);self.assertEqual(set(QLIN)&set(QNON),set());self.assertEqual(len(QALL),7)
 def test_q90_feature_refs(self):
  self.assertEqual(refs({"op":"feature_ref","namespace":"Q89","name":"lag_2"}),{"lag_2"})
 def test_q7_feature_refs(self):
  self.assertEqual(refs({"feature_ref":{"namespace":"Q7","feature_id":"number_frequency"}}),{"number_frequency"})
 def test_semantic_mask_order_independent(self):
  self.assertEqual(mask({"number_frequency","pair_interaction"},Q7_MAP),mask({"pair_interaction","number_frequency"},Q7_MAP))
 def test_linear_operator(self): self.assertEqual(op_type({"term":{"op":"mean"}}),"linear_mean")
 def test_interaction_operator(self):
  self.assertEqual(op_type({"term":{"op":"add","terms":[{"op":"scale","term":{"op":"candidate_zscore"}}]}}),"pairwise_interaction")
 def test_gate_operator(self):
  self.assertEqual(op_type({"term":{"op":"add","terms":[{"op":"scale","term":{"op":"indicator"}}]}}),"conditional_gate")
 def test_group_state_finite(self):
  rows=[{"a":str((i%4)/4),"b":str((i%3)/3)} for i in range(50)]
  x=group_state(rows,("a","b"));self.assertEqual(len(x),4);self.assertTrue(all(math.isfinite(v) for v in x))
 def test_group_state_rejects_out_of_range(self):
  with self.assertRaises(RuntimeError):group_state([{"a":"1.2","b":".2"} for _ in range(50)],("a","b"))
 def test_holm(self): self.assertEqual(holm([.04,.001]),[.04,.002])
 def test_canonical_json_stable(self): self.assertEqual(canon({"b":2,"a":1}),canon({"a":1,"b":2}));self.assertEqual(sha(canon({"a":1})),sha(canon({"a":1})))
 def test_strict_prior_excludes_current_future(self):
  rows=[{"ix":str(i),"v":str(i)} for i in range(10)]
  self.assertEqual([int(x["ix"]) for x in strict_prior_window(rows,list(range(10)),7,3,"ix")],[4,5,6])
 def test_future_suffix_mutation_invariance(self):
  rows=[{"ix":str(i),"v":str(i)} for i in range(10)];keys=list(range(10))
  before=strict_prior_window(rows,keys,7,3,"ix")
  rows[7:]=[{"ix":str(i),"v":"999"} for i in range(7,10)]
  after=strict_prior_window(rows,keys,7,3,"ix")
  self.assertEqual(before,after)
 def test_strict_prior_rejects_gap(self):
  rows=[{"ix":str(i)} for i in [0,1,3,4,5]]
  with self.assertRaises(RuntimeError):strict_prior_window(rows,[0,1,3,4,5],6,4,"ix")

if __name__=="__main__":unittest.main()
