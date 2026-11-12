import hashlib
import json
import os
from pathlib import Path
import pandas as pd

OUT = Path(os.environ.get('Q141_OUTPUT_DIR', '/mnt/data/q90_a5/outputs'))

def load_report():
    return json.loads((OUT/'q141_a5_b10_report.json').read_text())

def test_source_lineage_and_archive_prefix():
    r=load_report()
    assert r['source']['q90_archive_draws']==3401
    assert r['source']['q141_archive_draws']==3405
    assert r['source']['q90_is_exact_q141_prefix'] is True
    assert r['source']['q141_suffix_draws_excluded']==4
    assert r['lineage_audit']['artifact_member_count_verified']==17
    assert r['lineage_audit']['typed_ast_registry']['all_7_shard_remote_git_blob_sha1s_verified'] is True

def test_q90_grammar_and_feature_scope():
    r=load_report(); a=r['lineage_audit']
    assert a['formula_count']==330429
    assert a['formula_type_counts']=={'linear_mean':262599,'conditional_gate':38760,'pairwise_interaction':29070}
    assert a['feature_coverage']['total_source_features']==59
    assert a['feature_coverage']['selected_features']==20
    assert a['feature_coverage']['unselected_features']==39
    assert a['unique_base_feature_set_count']==262599
    assert a['four_feature_quartets']==4845
    assert a['variants_per_quartet']=={'linear_mean_L4':1,'pairwise_interaction_I4':6,'conditional_gate_G4':8}
    assert a['typed_ast_registry']['unique_ast_ids']==330429
    assert a['typed_ast_registry']['duplicate_ast_count']==0

def test_deterministic_formula_sample_and_balanced_weights():
    r=load_report(); s=r['sample']
    df=pd.read_csv(OUT/'q141_a5_b10_formula_sample.csv')
    assert len(df)==1900 and df.formula_id.nunique()==1900
    assert s['unique_base_feature_sets']==500
    assert s['base_group_size_distribution']=={'1':400,'15':100}
    sums=df.groupby('base_key').group_weight.sum()
    assert (sums.sub(1.0).abs()<1e-12).all()

def test_walkforward_strict_prior_and_split_counts():
    df=pd.read_csv(OUT/'q141_a5_b10_target_ledger.csv')
    assert len(df)==3351
    assert (df.target_date>df.cutoff_date).all()
    assert (df.prior_draws>=50).all()
    assert df.split.value_counts().to_dict()=={'discovery':2011,'validation':670,'blind_oos':670}
    assert df.target_date.is_monotonic_increasing

def test_formula_replay_matches_original_q90_metrics():
    df=pd.read_csv(OUT/'q141_a5_formula_replay_reconciliation.csv')
    assert set(df.split)=={'discovery','validation','blind_oos'}
    assert df.max_abs_mean_top5_share_diff_vs_q90_metrics.max()<1e-12

def test_primary_endpoint_not_promoted():
    r=load_report(); p=r['primary_blind_oos']
    assert p['confirmatory_endpoint_count']==1
    assert p['effect']<p['practical_threshold']
    assert p['ci95_circular_moving_block'][0]<0<p['ci95_circular_moving_block'][1]
    assert p['block_signflip_one_sided_p']>=0.05
    assert p['criteria_met'] is False
    assert r['decision']=='NO_BASE_SET_BALANCING_LIFT_DEMONSTRATED'

def test_manifest_hashes_and_checkpoint():
    m=json.loads((OUT/'q141_a5_b10_manifest.json').read_text())
    for name,meta in m['outputs'].items():
        b=(OUT/name).read_bytes()
        assert len(b)==meta['bytes']
        assert hashlib.sha256(b).hexdigest()==meta['sha256']
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==meta['git_blob_sha1']
    cp=json.loads((OUT/'q141_a5_b10_checkpoint.json').read_text())
    assert cp['status']=='LOCAL_REPLAY_COMPLETE_PENDING_OUTPUT_REMOTE_GIT_READBACK'
    assert cp['tests']['future_suffix_invariance'] and cp['tests']['target_outcome_invariance']
