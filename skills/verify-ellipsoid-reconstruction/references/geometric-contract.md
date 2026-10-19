# Geometric contract

## Shape and projection

Let E(c,S) = {x : (x−c)' S⁻¹ (x−c) ≤ 1}, S positive definite. Semiaxes are square roots of S's eigenvalues. With world-to-camera R and world camera center o, P = K R [I | −o]. The normalized dual quadric is Q* = [[S−cc',−c],[−c',−1]]. A plane π is tangent iff π'Q*π = 0. An image line ℓ lifts to π = P'ℓ; the dual image conic is D ∼ P Q* P'.

If the whole object must be in front, require c_c,z > sqrt(S_c,zz). A projected ellipse has D(m,T) = [[T−mm',−m],[−m',−1]], T positive definite. Its center is generally not the projection of c.

## Exact rank under complete ideal contours

For known finite calibrated cameras, known ID, an SPD ellipsoid and exact complete conics, eliminate each image's homogeneous multiplier. The 10-column symmetric-quadric design has ranks 5, 8 and 9 for one, two and at least three distinct camera centers. Three distinct collinear centers suffice for uniqueness; they do not guarantee good conditioning. Pure rotation has rank 5 regardless of image count.

With homogeneous camera centers k1,k2, Q*(λ) = Q* + λ(k1k2' + k2k1') preserves both conics. Small λ preserves physical shapes and strict front visibility. SPD constraints alone do not make two views unique. Unknown shape in one view has four degrees of ambiguity; fixing three semiaxes generically leaves one relative-pose degree.

Ellipse support is h(n)=n'm+sqrt(n'Tn). Cardinal bbox supports omit T12. If camera orientations agree and K has zero skew, varying Sxy can preserve every translated-view bbox. Check bbox tangent-design rank. A true ellipse's exact minimum-area OBB aligns with its axes; an arbitrary object's OBB need not satisfy this observation model.

## Partial visibility

A visible true silhouette tangent is also tangent to the full projection; an occluder-cut edge generally is not. Supplied boundary labels and normals are observation oracles even if 3D shape is unknown. For partial tangents use Gq=0 with rows svec(ππ')'; require rank 9 and physical validity. Declare normalization/tolerances. With noise, the tenth singular value need not be zero.

An exact nonempty open arc determines a conic algebraically, but arbitrarily short arcs can be arbitrarily ill-conditioned. Fully hidden objects supply no contour equations. Report missing information and abstention explicitly.

## Pose and identity

Unknown calibrated cameras and map retain Sim(3): c'=sGc+t, S'=s²GSG', o'=sGo+t, R'=RG'. Metric translations supply scale; an anchor fixes the frame. Sparse observations and symmetric maps can create further ambiguity. The count 5E ≥ 6M+9N−7 is necessary, not sufficient.

For bootstrapped static ID, distinguish labeled initialization, visible mapped detections, visible unmapped detections, false detections and reappearance. If assignment uses visibility, predict it from the reconstructed map. Do not supply hidden true map geometry to the predictor.

## Primary-source anchors

- Rubino et al., TPAMI 2018, DOI 10.1109/TPAMI.2017.2701373: dual reconstruction and two-view ambiguity; inspect bbox-to-ellipse observation construction separately.
- Nicholson et al., QuadricSLAM, RA-L 2019, arXiv:1804.04011: bbox plus odometry, known correspondence.
- Gaudillière et al., P1E, IJCV 2023, arXiv:2208.12513: known semiaxes; pin the version before adopting special-case classifications.
- Zins et al., arXiv:2203.04613 and arXiv:2207.07953: map-consistent ellipse prediction and known-map pose refinement; empirical occlusion behavior is not universal identifiability.

Verify formulas from definitions and primary texts. The rank argument above is independently derivable from projection; do not attribute a stronger theorem to a source without locating it.
