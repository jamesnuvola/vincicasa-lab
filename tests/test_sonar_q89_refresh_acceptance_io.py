#!/usr/bin/env python3
"""Regression test for Q89 acceptance CSV header/row materialization."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import validate_q89_refresh_delta as acceptance

class Q89RefreshAcceptanceCsvTests(unittest.TestCase):
    def test_single_reader_preserves_header_and_all_data_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fixture.csv"
            path.write_text("target_date,value\n2026-11-01,10\n2026-11-02,20\n2026-11-03,30\n",encoding="utf-8")
            fields,rows=acceptance.read_csv_fields_rows(path)
            self.assertEqual(fields,["target_date","value"])
            self.assertEqual(len(rows),3)
            self.assertEqual([row["target_date"] for row in rows],["2026-11-01","2026-11-02","2026-11-03"])
            self.assertEqual([row["value"] for row in rows],["10","20","30"])

if __name__=="__main__":
    unittest.main()
