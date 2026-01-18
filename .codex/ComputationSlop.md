 # Detecting Premature and Saturation Points in log–log Plots

 When plotting the interface width g vs mean height h (or simulation time t) on log–log axes, one typically observes three regimes:
 1. Initial transient (ballistic) growth:    g ∼ h^β₁  (β₁ ≈ 1/2)
 2. Middle scaling growth:                 g ∼ h^v   (v ≈ 0.3 in 2D)
 3. Saturation plateau:                    g → constant g_sat

 We need to identify:
 - Premature point (h_p): end of the initial transient, start of true power‐law growth.
 - Saturation point (h_s): start of the plateau regime.

 ## 1. Local‐slope (derivative) method
 1. Compute x_i = log₁₀(h_i), y_i = log₁₀(g_i).
 2. Compute centered difference slopes:
        m_i = (y_{i+1} − y_{i−1}) / (x_{i+1} − x_{i−1}).
 3. Let v be the fitted exponent in the scaling regime.
 4. **h_p**: the first h_i where m_i enters and remains within [v − Δ, v + Δ] (Δ ~10%).
 5. **h_s**: the first h_i where m_i falls below a small threshold ε (e.g. ε ~ 0.1), indicating flattening.

 ## 2. Two‐asymptote intersection method
 1. Fit early data to y = β₁ x + B₁ (β₁ ~ 1/2).
 2. Fit middle data to y = v x + B₂.
 3. Fit late data to y = log₁₀(g_sat) (horizontal line).
 4. Solve:
       x_p = (B₂ − B₁)/(β₁ − v)      ⟹  h_p = 10^{x_p}
       x_s = (log₁₀(g_sat) − B₂)/v   ⟹  h_s = 10^{x_s}

 ## Computing the exponent between h_p and h_s
 Once h_p and h_s are identified, the effective exponent v_eff is
   v_eff = (log₁₀ g(h_s) − log₁₀ g(h_p)) / (log₁₀ h_s − log₁₀ h_p).
 This “endpoint slope” often matches the least‐squares fit in the intermediate regime.

## 3. Local‐slope (median) method
Instead of choosing arbitrary thresholds, compute the local slope m_i = d log g / d log h via centered finite differences:
  m_i = [log g(h_{i+1}) − log g(h_{i−1})] / [log h_{i+1} − log h_{i−1}].
Then take v_eff = median(m_i) over all valid i (i=1…N−2).  This naturally downweights both:
  - startup regime (m≈½) and
  - saturation regime (m≈0)
leaving the central cluster of slopes ≃1/3.

## 4. Quantile‐based error bound
To assign an uncertainty on the slope estimates, we use two complementary approaches:

- Local‐slope (median) error: compute the 25th percentile (q25) and 75th percentile (q75) of the centered‐difference slopes m_i, and define the half‐interquartile range
  
    half-IQR = (q75 − q25) / 2

  This half-IQR provides a robust uncertainty estimate on the median slope (≈1σ if the central distribution is approximately normal).

- Endpoint‐slope regression error: when fitting the two endpoints (h_p, h_s) via least‐squares on the log–log data,
  the standard error of the slope is given by

    stderr = sqrt[ Σ(residuals²) / ((n − 2) · Σ(x_i − x̄)²) ],

  where residuals are the differences between the data and the regression line, x_i = log₁₀(h_i), and n is the number of points between h_p and h_s.  In practice, libraries such as SciPy’s `linregress` return this `stderr` directly.

## 5. Global sliding‐window polyfit method

The `ComputeSlope()` routine performs a series of global log–log fits over increasing time windows, yielding a time‐resolved growth exponent:

1. Choose an initial cut‐off step, e.g. `t0 = 10`.
2. Define a sequence of end steps `t_j` spanning from `t0` to the final step `T`, sampling at most 100 points uniformly.
3. For each `t_j`, fit the data
       x = log10([1, 2, …, t_j]),
       y = log10([g(1), g(2), …, g(t_j)])
   to a straight line `y = m_j x + b_j` via least squares; record the slope `m_j`.
4. Store the pairs `(log10(t_j), m_j)` in the output array `log_time_slopes`.
5. The resulting curve of `m_j` vs. `log10(t_j)` reveals how the effective exponent approaches its asymptote over time.

This sliding‐window polyfit method captures the transient relaxation of the growth exponent, and can be used to identify when the system enters its true scaling regime.

## 6. Simulation length and saturation detection

In the current implementation, each Tetris‐Ballistic simulation is run up to a fixed maximum number of steps

```python
steps = ratio * width * width
```
or until the lattice completely fills (a “Game Over” when the height limit is reached).  There is no early‐stop upon reaching saturation in the fluctuation.

Instead, saturation is detected in post‐processing via the `ComputeEndpointSlope(low_threshold, high_threshold)` routine:

1. **Compute maximum fluctuation**:  `F_max = max( Fluctuation[0:FinalSteps] )`
2. **Find saturation time**:  the first index `t_s` where `Fluctuation[t_s] >= high_threshold * F_max` (default `high_threshold = 0.9`).
3. **Find premature time**:  similarly with `low_threshold = 0.1`.
4. **Endpoint slope**: the slope between `(log10(t_p), log10(F(t_p)))` and `(log10(t_s), log10(F(t_s)))`.

This threshold‐crossing approach localizes the true start of the power‐law and
the onset of the plateau, without altering the simulation run length.  You may
adjust `low_threshold` and `high_threshold` to tune sensitivity to early‐time
transients or noise in the tail.

