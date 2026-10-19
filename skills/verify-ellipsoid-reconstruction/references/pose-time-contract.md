# Approximate poses, clocks and shared errors

Define camera-to-world `F(t)`, image time `t_i`, pose-clock time `s_l`, and the sign convention before differentiating. If `P_i = K [I|0] F(t_i + tau)^-1`, positive `tau` queries a later pose-clock time. Preserve the original image timestamp when a detector result arrives late: arrival latency alone need not create a geometric clock unknown. Temporal smoothing, rolling shutter, drift and per-frame delay require separate models.

Separate the source of world coordinates and metric scale. Noisy absolute poses supply an uncertain metric frame; a first-pose gauge choice does not make a noisy measurement exact. Report absolute-frame shape errors before any optional diagnostic alignment. A common location error can fail many small objects while their axes and reprojections remain accurate.

For constant spatial twist `F(t)=exp(t Xi)F0`, changing `tau` to `tau+delta` and every object by `exp(delta Xi)` preserves camera-coordinate points, projection, depth ordering and mutual occlusion. Known object size alone does not remove this ambiguity. Construct the transformation, not only a numerically small singular value.

For free image-pose corrections `F_i = Fbar(t_i+tau) exp(xi_i)`, change `xi_i` to `Log(Fbar(t_i+tau')^-1 F_i)`. The actual cameras and all ellipses stay fixed. Image-only clock information is absent; an informative result uses pose observations, a constrained curve, bounds or clock priors. Finite knot count alone is not sufficient if the knot-to-image map can represent arbitrary image poses locally.

Trace residual timestamps. In a knot-based estimator, pose measurement residuals belong at fixed pose-clock times `s_l`; only image queries use `t_i+tau`. Interpolation can correlate errors across image poses. Independent correction priors are an approximation; if a shared curve is used, include every genuinely dependent knot in Jacobian sparsity. Do not falsely improve timing by clamping queries outside the curve domain.

Define exactly which local matrix is reported. A fixed IRLS matrix from raw residual Jacobians and fixed `rho'(s)` weights differs from the Gauss-Newton matrix of a differentiated radial residual transform. Record support normalization, parameter units, the eliminated nuisance variables and prior contributions. Neither matrix is automatically Fisher information or a calibrated covariance. Sixteen supports reconstructed from one five-parameter ellipse have local covariance rank at most five.

Use full-column rank as a local sufficient condition at regular points; do not use rank deficiency as the converse for arbitrary nonlinear maps. Keep exact ambiguity constructions, first-order information tests, finite experiments and calibrated uncertainty claims separate.

Validate every start boundary: all invalid, one invalid, ordinary valid, and optional information diagnostics with no clock variable. Save failures before any post-fit projection that can throw. A converged constant-penalty invalid state is a failure. Keep the full object/scene population even when no detection, no initialization or no valid estimate exists.

Compare common observations and initial shapes separately from compute budget. A robust continuation after another solver has extra computation. Use new development/evaluation namespaces when scene generators share random seeds. Preserve an already-started or failed pilot with its exclusion reason; never silently relabel it as a new heldout scene.


## Calibrated improvement and reproduction claims

When replacing image-time pose corrections with raw measurement knots, list the representation change, residual coordinates, covariance calibration, optimizer continuation, and any added motion prior separately. A successful comparison of the combined change does not isolate one component's causal effect. A process prior expressed as unscaled high-order discrete differences depends on knot spacing and units; do not transfer its weights unchanged to another sampling interval.

A single-scene reproduction can verify numerical reproducibility while failing the registered-cohort adoption check. Formal success gates require the complete declared roster and population. Preserve the original summary when correcting a reporting bug, record source import/freeze chronology, and keep replay outputs separate from both development and evaluation evidence. Replaying a previously inspected seed is not fresh validation.
