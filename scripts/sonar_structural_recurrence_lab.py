#!/usr/bin/env python3
"""Append-only structural signature generator for the VinciCasa SONAR lab."""
from __future__ import annotations
import argparse, csv
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIELDS="date numbers sum range odd even low_le20 high_gt20 overlap_prev1 gap1 gap2 gap3 gap4 sum_bin range_bin odd_cat low_cat overlap_cat gap1_bin gap2_bin gap3_bin gap4_bin sum_delta range_delta sum_transition range_transition mean_gap".split()

def bucket(x, edges, labels):
    return labels[next((i for i,e in enumerate(edges) if x<e),len(edges))]
