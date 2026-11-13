import math
import unittest
from scripts.sonar_q142_rule_family_fwer_audit import binomial_tail, holm, parse_numbers, split_bounds, validate_row, spearman

class Q142AuditTests(unittest.TestCase):
    def test_exact_top20_5of5_null(self):
        self.assertAlmostEqual(math.comb(20,5)/math.comb(40,5),0.02356202356202356,places=15)
    def test_exact_top20_4plus_null(self):
        p=(math.comb(20,4)*math.comb(20,1)+math.comb(20,5))/math.comb(40,5)
        self.assertAlmostEqual(p,0.17082467082467082,places=15)
    def test_binomial_tail_edges_and_monotonicity(self):
        self.assertEqual(binomial_tail(10,0,0.2),1.0)
        self.assertEqual(binomial_tail(10,11,0.2),0.0)
        self.assertGreater(binomial_tail(100,10,0.1),binomial_tail(100,15,0.1))
    def test_holm_adjustment(self):
        got=holm([{"p_raw":0.01},{"p_raw":0.04},{"p_raw":0.03}])
        self.assertEqual([round(x["p_holm"],8) for x in got],[0.03,0.06,0.06])
    def test_split_lengths(self):
        self.assertEqual(split_bounds(3206),(1923,2564))
    def test_spearman_identity_and_reverse(self):
        self.assertAlmostEqual(spearman([1,2,3,4],[1,2,3,4]),1.0)
        self.assertAlmostEqual(spearman([1,2,3,4],[4,3,2,1]),-1.0)
    def test_parse_numbers_rejects_duplicates(self):
        with self.assertRaises(ValueError):
            parse_numbers("1 2 2 4 5",5,True)
    def test_target_row_checks_cutoff_actual_and_hits(self):
        row={"target_date":"2026-11-13","history_cutoff":"2026-11-12","actual_numbers":"2 4 7 23 33",
             "top20":"2 4 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24",
             "hit_count":"4","all5_top20":"0","evaluation_mode":"RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW","config_id":"fixture"}
        self.assertEqual(validate_row(row,"2026-11-12",(2,4,7,23,33)),4)
        with self.assertRaises(ValueError):
            validate_row(row,"2026-11-11",(2,4,7,23,33))
        bad=dict(row,hit_count="5")
        with self.assertRaises(ValueError):
            validate_row(bad,"2026-11-12",(2,4,7,23,33))

if __name__=="__main__":
    unittest.main()
