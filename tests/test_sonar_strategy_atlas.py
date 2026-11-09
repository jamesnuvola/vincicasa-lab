#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, importlib.util, json, tempfile, unittest
from datetime import date, timedelta
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("q84",ROOT/"scripts/sonar_strategy_atlas.py")
q84=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(q84)
def make_csv(path,n=80):
    rows=[]
    for i in range(n):
        vals=sorted({((i*7+k*11)%40)+1 for k in range(5)})
        if len(vals)!=5:raise AssertionError("synthetic quintet is not unique")
        rows.append([(date(2020,1,1)+timedelta(days=i)).isoformat(),*vals])
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(["data","n1","n2","n3","n4","n5"]);w.writerows(rows)
def validate_ledger(path,expected_dates=None):
    with path.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    if expected_dates is not None and [r["target_date"] for r in rows]!=expected_dates:raise AssertionError("target dates do not reconcile")
    rank_cols=[c for c in rows[0] if c.startswith("rank_vector_")]
    actual_cols=[c for c in rows[0] if c.startswith("actual_ranks_")]
    if len(rank_cols)!=51 or len(actual_cols)!=51:raise AssertionError(f"rank-vector column counts {len(rank_cols)}/{len(actual_cols)}")
    for i,r in enumerate(rows):
        if not r["cutoff_date"]<r["target_date"]:raise AssertionError("target leakage in cutoff")
        if int(r["prior_draws"])!=i+50:raise AssertionError("prior_draws index mismatch")
        actual=[int(x) for x in r["actual_quintet"].split()]
        if len(actual)!=5 or actual!=sorted(set(actual)):raise AssertionError("invalid actual quintet")
        for rc in rank_cols:
            v=r[rc]
            if len(v)!=40 or set(v)!=set(q84.ALPHA):raise AssertionError("rank vector is not a 1..40 permutation")
            ac="actual_ranks_"+rc[len("rank_vector_"):]
            expected="".join(v[n-1] for n in actual)
            if r[ac]!=expected:raise AssertionError("actual rank vector does not reconcile")
        union_cols=[c for c in r if c.startswith("candidate_union_numbers_")]
        if len(union_cols)!=12:raise AssertionError("candidate union columns incomplete")
        for uc in union_cols:
            nums=[q84.ALPHA.index(ch)+1 for ch in r[uc]]
            suffix=uc[len("candidate_union_numbers_"):]
            size=int(r["candidate_union_size_"+suffix])
            hits=int(r["candidate_union_actual_hits_"+suffix])
            exp=float(r["candidate_union_expected_hits_"+suffix])
            if not 5<=len(nums)<=10 or len(nums)!=len(set(nums)) or size!=len(nums):raise AssertionError("union set size mismatch")
            if hits!=sum(n in nums for n in actual):raise AssertionError("union actual hits mismatch")
            if abs(exp-5*size/40)>1e-12:raise AssertionError("union expected hits mismatch")
    return rows
class Q84AtlasTests(unittest.TestCase):
    def test_holm_and_rank_tie_break(self):
        self.assertEqual(q84.holm([.01,.04,.03]),[.03,.06,.06])
        self.assertEqual(q84.rank_vector(np.ones(40)).tolist(),list(range(1,41)))
        scores=np.ones((40,351));r=q84.rank_actual_pair(scores,np.array([0,1,2,3,4]))
        self.assertTrue(np.all(r[:,0]==np.array([1,2,3,4,5])))
    def test_synthetic_walkforward_and_artifact_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);arch=d/"synthetic.csv";out=d/"reports";make_csv(arch)
            old_arch,old_out=q84.ARCH,q84.OUT
            try:q84.ARCH=arch;q84.OUT=out;q84.main()
            finally:q84.ARCH, q84.OUT=old_arch,old_out
            report=json.loads((out/"strategy_atlas_report.json").read_text())
            self.assertEqual(report["archive"]["draw_count"],80)
            self.assertEqual(report["archive"]["eligible_target_count"],30)
            self.assertEqual(report["split_counts"],{"discovery":18,"validation":6,"blind_oos":6})
            self.assertEqual(report["finite_grammar"]["catalog_records"],730)
            self.assertEqual(report["multiple_testing"]["performance_family_tests"],4536)
            self.assertEqual(report["multiple_testing"]["pair_union_conditional_hypergeometric_tests"],1053)
            self.assertEqual(report["multiple_testing"]["pair_gain_analytic_normal_tests"],1053)
            self.assertEqual(report["multiple_testing"]["conditional_state_tests"],153)
            self.assertEqual(report["multiple_testing"]["selected_pair_block_bootstrap_tests"],48)
            catalog=[json.loads(x) for x in (out/"strategy_atlas_catalog.jsonl").read_text().splitlines()]
            self.assertEqual(len(catalog),730);self.assertEqual(len({x["strategy_id"] for x in catalog}),730)
            life=json.loads((out/"strategy_atlas_lifecycle.json").read_text());self.assertEqual(len(life["strategies"]),730)
            ledger=validate_ledger(out/"strategy_atlas_target_ledger.csv")
            self.assertEqual(len(ledger),30)
            for fn,key in [("strategy_atlas_catalog.jsonl","strategy_atlas_catalog_jsonl"),("strategy_atlas_target_ledger.csv","strategy_atlas_target_ledger_csv"),("strategy_atlas_lifecycle.json","strategy_atlas_lifecycle_json")]:
                data=(out/fn).read_bytes();sha=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
                self.assertEqual(report["artifact_checksums"][key],sha)
if __name__=="__main__":unittest.main(verbosity=2)
