#!/usr/bin/env python3
"""Unit tests for Q141-A3 typed Q90 AST construction and canonicalization."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_q90_ast_import as importer


NAMES = ["f0", "f1", "f2", "f3", "f4"]
FAMILIES = {name: "test_family" for name in NAMES}


class Q90AstImportTests(unittest.TestCase):
    def test_linear_mean_canonicalizes_commutative_terms(self):
        row = {
            "formula_id": "L4_test",
            "formula_type": "linear_mean",
            "formula_size": "4",
            "feature_indices": "3;1;0;2",
            "features": "f3+f1+f0+f2",
            "interaction_pair": "",
            "gate_feature": "",
            "gate_threshold": "",
            "weight": "",
            "search_source": "discovery_selected_feature_subset",
        }
        ast, ast_id = importer.build_ast(row, NAMES, FAMILIES)
        self.assertEqual([x["index"] for x in ast["term"]["terms"]], [0, 1, 2, 3])
        self.assertTrue(ast_id.startswith("Q90AST1-"))
        self.assertEqual(ast_id, importer.ast_identifier(ast))

    def test_pairwise_product_pair_is_commutative_and_rational(self):
        row = {
            "formula_id": "I4_test",
            "formula_type": "pairwise_interaction",
            "formula_size": "4",
            "feature_indices": "0;1;2;3",
            "features": "f0+f1+f2+f3",
            "interaction_pair": "f2*f0",
            "gate_feature": "",
            "gate_threshold": "",
            "weight": "0.25",
            "search_source": "discovery_selected_feature_subset",
        }
        ast, _ = importer.build_ast(row, NAMES, FAMILIES)
        factors = ast["term"]["terms"][1]["term"]["term"]["factors"]
        self.assertEqual([x["index"] for x in factors], [0, 2])
        self.assertEqual(ast["term"]["terms"][1]["coefficient"], {"numerator": 1, "denominator": 4})

    def test_conditional_gate_uses_rational_threshold_and_bonus(self):
        row = {
            "formula_id": "G4_test",
            "formula_type": "conditional_gate",
            "formula_size": "4",
            "feature_indices": "0;1;2;3",
            "features": "f0+f1+f2+f3",
            "interaction_pair": "",
            "gate_feature": "f2",
            "gate_threshold": "0.5",
            "weight": "0.25",
            "search_source": "discovery_selected_feature_subset",
        }
        ast, _ = importer.build_ast(row, NAMES, FAMILIES)
        condition = ast["term"]["terms"][1]["term"]["condition"]
        self.assertEqual(condition["left"]["index"], 2)
        self.assertEqual(condition["right"], {"numerator": 1, "denominator": 2})

    def test_invalid_interaction_pair_is_rejected(self):
        row = {
            "formula_id": "I4_bad",
            "formula_type": "pairwise_interaction",
            "formula_size": "4",
            "feature_indices": "0;1;2;3",
            "features": "f0+f1+f2+f3",
            "interaction_pair": "f0*f4",
            "gate_feature": "",
            "gate_threshold": "",
            "weight": "0.25",
            "search_source": "discovery_selected_feature_subset",
        }
        with self.assertRaises(ValueError):
            importer.build_ast(row, NAMES, FAMILIES)

    def test_q90_formula_count_is_nested_in_formula_grammar(self):
        manifest = {"formula_grammar": {"formula_count": 330429, "formula_type_counts": importer.EXPECTED_FORMULA_COUNTS}}
        self.assertEqual(importer.q90_formula_count(manifest), 330429)

    def test_git_blob_sha1_uses_canonical_nul_header(self):
        data = b"abc"
        self.assertEqual(importer.git_blob_sha1(data), hashlib.sha1(b"blob 3\0abc").hexdigest())

    def test_deterministic_gzip_shard_bytes(self):
        records = [
            {"ast_id": "a", "source_formula_id": "L4_a"},
            {"ast_id": "b", "source_formula_id": "L4_b"},
            {"ast_id": "c", "source_formula_id": "L4_c"},
        ]
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            writer_a = importer.ShardWriter(Path(a), shard_rows=2)
            writer_b = importer.ShardWriter(Path(b), shard_rows=2)
            for row in records:
                writer_a.write(row)
                writer_b.write(row)
            writer_a.close()
            writer_b.close()
            self.assertEqual(len(writer_a.shards), 2)
            self.assertEqual([item["rows"] for item in writer_a.shards], [2, 1])
            self.assertEqual(
                (Path(a) / writer_a.shards[0]["path"]).read_bytes(),
                (Path(b) / writer_b.shards[0]["path"]).read_bytes(),
            )
            self.assertEqual(
                (Path(a) / writer_a.shards[1]["path"]).read_bytes(),
                (Path(b) / writer_b.shards[1]["path"]).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
