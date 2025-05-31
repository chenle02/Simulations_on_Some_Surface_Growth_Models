 # Detecting Premature and Saturation Points in log–log Plots

 When plotting the interface width g vs mean height h (or simulation time t) on log–log axes, one typically observes three regimes:
 1. Initial transient (ballistic) growth:    g ∼ h^β₁  (β₁ ≈ 1)
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
 1. Fit early data to y = β₁ x + B₁ (β₁ ~ 1).
 2. Fit middle data to y = v x + B₂.
 3. Fit late data to y = log₁₀(g_sat) (horizontal line).
 4. Solve:
       x_p = (B₂ − B₁)/(β₁ − v)   ⟹ h_p = 10^{x_p}
       x_s = (log₁₀(g_sat) − B₂)/v   ⟹ h_s = 10^{x_s}

 ## Computing the exponent between h_p and h_s
 Once h_p and h_s are identified, the effective exponent v_eff is
   v_eff = (log₁₀ g(h_s) − log₁₀ g(h_p)) / (log₁₀ h_s − log₁₀ h_p).
 This “endpoint slope” often matches the least‐squares fit in the intermediate regime.