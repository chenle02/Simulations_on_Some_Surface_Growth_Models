# KPZ analysis currentness contract

The slope-analysis cache is a scientific artifact, not an existence check.
Every reusable JSON payload has a sibling `*.manifest.json` commit marker and
a persistent `*.lock`. The payload alone is never evidence of a completed or
current calculation.

## Input boundary

The runner accepts one layout per invocation:

- `reduced`: one exact `pct_NN/L_LLLL.npz` archive per requested ensemble.
  Two closed schema variants are accepted. The base schema has the eight
  fields written by the reducer; historical exp13 `seeds` and `final_steps`
  may be little-endian `int32`, while the current reducer writes little-endian
  `int64`. The corrected-exp14 variant adds one `int32` scalar `height_grid`,
  which must equal the declared `ratio:auto, sat_margin:3` grid height. The
  archive inventory, NPY headers, dtypes, shapes, embedded percentage/width,
  ordered seeds, exact `min(final_steps)` truncation, finite nonnegative
  observables, nondecreasing physical mean height, `hbar_max`, and saturation
  flag are validated before use. Any other member or encoding is rejected.
- `legacy-flat`: historical flat joblibs, selected explicitly. This path
  validates the filename against embedded width, seed, one-cell model
  configuration, percentage convention, real finite observables, and a
  nondecreasing physical mean-height clock, but still executes trusted Python
  pickle data. Never use it for an untrusted file.

Managed hierarchical simulation outputs are not direct inputs. Validate and
reduce the declared grid first with `scripts.reduce_traces`; analysis then
targets the resulting trace root. Reduced NPZ bytes are the S0.4 analysis
boundary. A cross-repository raw-to-reduction bundle lineage remains an S4
result-bundle task.

The reduced schemas do not themselves encode the percentage convention or
executable model. For reduced input, those declarations remain an operator and
experiment-provenance responsibility until S4 adds raw-to-reduction lineage.
The runner identity-binds the supplied declarations so they cannot be changed
silently when a cache is resumed or aggregated. The legacy-flat path can also
check them against its embedded configuration.

## Identity and reuse

Each cell manifest binds:

- the exact requested percentage, width, ordered seed inventory, and trace
  file bytes;
- `sticky-fraction` versus `nonsticky-fraction` semantics;
- the `piece-19-one-cell-v1` executable model profile;
- every exposed estimator setting, minimum ensemble size, and sampling policy;
- bootstrap generator, stream policy, and seed;
- the package Python-tree digest, Python runtime, and numerical dependency
  versions, plus the source-declared version when run from a checkout and the
  installed distribution-metadata version when available.

`--resume` computes missing cells and reuses only an exact identity match.
Corrupt, partial, stale, or mismatched artifacts stop the run. After reviewing
the discrepancy, `--replace` is the explicit regeneration operation.
`--aggregate-only` requires the same closed percentage-by-width grid and
rebuilds summaries from validated cells; it never globs old summaries.
The managed CLI will not publish below 10 independent runs per ensemble or 200
case-bootstrap replicates. Low-count calls to estimator functions are
exploratory and are outside this managed publication contract.

## Publication and failure behavior

Writers hold persistent advisory locks, use unique same-directory temporary
files, fsync file and directory state, publish the payload first, and publish
the manifest last. Input inventories and hashes are checked before and after a
calculation. Per-percentage and grid summaries lock and revalidate all claimed
children while deriving their dependency records. The final reader recomputes
the full dependency snapshot before accepting `results.json`.

At the start of a requested generation, old summary commit markers and the
requested diagnostic plots are withdrawn. Thus a failed rerun cannot leave an
older result looking current. A late failure withdraws those products again,
including any diagnostic written earlier in the failed generation. JSON plus
its validating manifest is
authoritative; PNG files are non-authoritative diagnostics and are regenerated
from the validated cell grid. Plot titles carry both the percentage convention
and the `Piece-19 one-cell` model label so exported diagnostics retain their
basic scientific context.

Undefined estimates are encoded as JSON `null`; NaN and Infinity are never
written. Bare JSON, orphaned manifests, duplicate keys, nonfinite constants,
checksum changes, mixed child identities, and percentage/model confusion all
fail closed. For reduced archives, this means disagreement with the bound
operator declaration; the archive alone cannot prove that declaration before
the S4 lineage bundle exists.
