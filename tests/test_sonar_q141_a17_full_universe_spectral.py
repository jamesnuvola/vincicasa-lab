import unittest
import numpy as np

from sonar_q141_a17_full_universe_spectral import (
    apply_independent_circular_shifts,
    block_bootstrap_ci,
    circular_shift_surrogates,
    fit_basis,
    holm_adjust,
    project_capture,
    row_center_and_scale,
    split_slices,
    validate_alignment,
    validate_initial_unscored_row,
)

class Q141A17Tests(unittest.TestCase):
    def test_split_counts_are_frozen(self):
        ranges = split_slices(2986)
        counts = {name: sl.stop - sl.start for name, sl in ranges.items()}
        self.assertEqual(counts, {"discovery": 1792, "validation": 597, "blind_oos": 597})
        self.assertEqual(ranges["discovery"].start, 400)
        self.assertEqual(ranges["blind_oos"].stop, 3386)

    def test_fit_basis_is_orthonormal_and_sign_canonical(self):
        rng = np.random.default_rng(17)
        latent = rng.normal(size=(120, 3))
        mixing = rng.normal(size=(3, 24))
        x = latent @ mixing + 0.01 * rng.normal(size=(120, 24))
        basis, eigenvalues = fit_basis(x, 3)
        np.testing.assert_allclose(basis.T @ basis, np.eye(3), atol=1e-12)
        self.assertTrue(np.all(eigenvalues[:-1] >= eigenvalues[1:]))
        for j in range(3):
            pivot = np.argmax(np.abs(basis[:, j]))
            self.assertGreaterEqual(basis[pivot, j], 0.0)

    def test_projection_capture_is_one_for_vector_in_subspace(self):
        rng = np.random.default_rng(18)
        raw = rng.normal(size=(80, 12))
        basis, _ = fit_basis(raw, 4)
        vector = basis[:, 0] * 3.0 - basis[:, 2] * 2.0
        capture = project_capture(vector.reshape(1, -1), basis)[0]
        self.assertAlmostEqual(float(capture), 1.0, places=12)

    def test_row_center_and_scaler_use_training_prefix_only(self):
        rng = np.random.default_rng(19)
        ranks = rng.integers(1, 658009, size=(430, 16), dtype=np.int32)
        z1, means1, scales1 = row_center_and_scale(ranks, 400)
        changed = ranks.copy()
        changed[400:] = rng.integers(1, 658009, size=changed[400:].shape, dtype=np.int32)
        z2, means2, scales2 = row_center_and_scale(changed, 400)
        np.testing.assert_array_equal(means1, means2)
        np.testing.assert_array_equal(scales1, scales2)
        np.testing.assert_array_equal(z1[:400], z2[:400])

    def test_future_suffix_cannot_change_frozen_basis(self):
        rng = np.random.default_rng(20)
        x = rng.normal(size=(430, 24))
        basis1, _ = fit_basis(x[:400], 6)
        x[400:] = rng.normal(loc=100.0, scale=20.0, size=x[400:].shape)
        basis2, _ = fit_basis(x[:400], 6)
        np.testing.assert_array_equal(basis1, basis2)

    def test_independent_circular_shifts_preserve_each_column_multiset(self):
        rng = np.random.default_rng(21)
        x = rng.normal(size=(100, 9))
        shifts = rng.integers(1, 100, size=9)
        shifted = apply_independent_circular_shifts(x, shifts)
        for col in range(x.shape[1]):
            np.testing.assert_array_equal(np.sort(x[:, col]), np.sort(shifted[:, col]))
        self.assertFalse(np.array_equal(x, shifted))

    def test_circular_shift_null_is_deterministic(self):
        rng = np.random.default_rng(22)
        x = rng.normal(size=(420, 12))
        ranges = {"discovery": slice(400, 412), "validation": slice(412, 416), "blind_oos": slice(416, 420)}
        a = circular_shift_surrogates(x, ranges, replicates=3, seed=23)
        b = circular_shift_surrogates(x, ranges, replicates=3, seed=23)
        for name in ranges:
            np.testing.assert_array_equal(a[name], b[name])
            self.assertEqual(a[name].shape, (3,))

    def test_holm_adjustment(self):
        adjusted = holm_adjust([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06], atol=1e-12)

    def test_block_bootstrap_is_reproducible_and_ordered(self):
        values = np.linspace(0.2, 0.8, 80)
        a = block_bootstrap_ci(values, seed=24, replicates=500, block=10)
        b = block_bootstrap_ci(values, seed=24, replicates=500, block=10)
        self.assertEqual(a, b)
        self.assertLessEqual(a[0], a[1])
        self.assertTrue(0.0 <= a[0] <= 1.0)
        self.assertTrue(0.0 <= a[1] <= 1.0)


    def test_initial_insufficient_history_row_is_excluded_and_reconciled(self):
        dates = ["2017-07-17", "2017-07-18"]
        draws = [(12, 16, 20, 31, 32), (10, 12, 23, 37, 39)]
        self.assertTrue(validate_initial_unscored_row(
            dates[0], "", "0", "12 16 20 31 32", "INSUFFICIENT_HISTORY",
            [""] * 8, dates, draws
        ))
        self.assertFalse(validate_initial_unscored_row(
            dates[0], dates[0], "0", "12 16 20 31 32", "INSUFFICIENT_HISTORY",
            [""] * 8, dates, draws
        ))
        self.assertFalse(validate_initial_unscored_row(
            dates[0], "", "0", "12 16 20 31 32", "SCORED",
            [""] * 8, dates, draws
        ))

    def test_strict_prior_alignment_checks_cutoff_target_and_outcome(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
        draws = [(1, 2, 3, 4, 5), (2, 4, 6, 8, 10), (3, 6, 9, 12, 15)]
        self.assertTrue(validate_alignment(0, dates[1], dates[0], 1, "2 4 6 8 10", dates, draws))
        self.assertFalse(validate_alignment(0, dates[1], dates[1], 1, "2 4 6 8 10", dates, draws))
        self.assertFalse(validate_alignment(0, dates[1], dates[0], 2, "2 4 6 8 10", dates, draws))
        self.assertFalse(validate_alignment(0, dates[1], dates[0], 1, "1 2 3 4 5", dates, draws))

if __name__ == "__main__":
    unittest.main()
