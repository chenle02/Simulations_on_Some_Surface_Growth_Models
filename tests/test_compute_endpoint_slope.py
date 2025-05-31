import numpy as np
import pytest

from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_compute_endpoint_slope_power_law():
    """
    For a perfect power-law fluctuation Fluc(t) = t^2, on 100 steps,
    the 10% threshold occurs when t ≈ sqrt(0.1)*100 ≈ 31.6 → index 31 (0-based),
    and the 50% threshold at t ≈ sqrt(0.5)*100 ≈ 70.7 → index 70.
    The endpoint slope should be ≈2.0 exactly.
    """
    # Initialize with dummy parameters; we'll override fluctuation directly
    tb = Tetris_Ballistic(width=10, height=10, steps=100, seed=0)
    N = 100
    # Create fluctuation = t^2 for t=1..100
    tb.Fluctuation = np.arange(1, N+1, dtype=float) ** 2
    tb.FinalSteps = N

    low_idx, high_idx, slope = tb.ComputeEndpointSlope(low_threshold=0.1,
                                                        high_threshold=0.5)
    # Check that the thresholds fall at the expected indices
    assert low_idx == 31, f"Expected low index 31, got {low_idx}"
    assert high_idx == 70, f"Expected high index 70, got {high_idx}"
    # The exact power-law exponent is 2
    assert pytest.approx(slope, rel=1e-6) == 2.0

def test_compute_endpoint_slope_constant():
    """
    If fluctuation is constant, slopes are undefined (division by zero);
    function should handle gracefully, possibly returning inf or nan.
    """
    tb = Tetris_Ballistic(width=5, height=5, steps=50, seed=1)
    N = 50
    tb.Fluctuation = np.ones(N)
    tb.FinalSteps = N
    low_idx, high_idx, slope = tb.ComputeEndpointSlope(low_threshold=0.1,
                                                        high_threshold=0.9)
    # low and high thresholds both hit at index 0
    assert low_idx == 0
    assert high_idx == 0
    # slope will be nan or inf; test for nan
    assert np.isnan(slope) or np.isinf(slope)
    
def test_compute_slope_local_power_law():
    """
    For a perfect power-law fluctuation Fluc(t) = t^3, local slopes = 3,
    so median slope = 3.0 and half-IQR = 0.0.
    """
    tb = Tetris_Ballistic(width=5, height=5, steps=50, seed=2)
    N = 50
    tb.Fluctuation = np.arange(1, N+1, dtype=float) ** 3
    tb.FinalSteps = N
    logT, slopes, med, half_iqr = tb.ComputeSlopeLocal()
    # slopes length
    assert len(slopes) == N - 2
    # all slopes approx 3.0
    assert np.allclose(slopes, 3.0, atol=1e-6)
    # median = 3.0, half-IQR = 0
    assert pytest.approx(med, rel=1e-6) == 3.0
    assert abs(half_iqr) < 1e-12

# Removed ComputeSlopeLocalStats; tested via ComputeSlopeLocal above