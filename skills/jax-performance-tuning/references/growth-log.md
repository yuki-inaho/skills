# Growth log — jax-performance-tuning

Generic, non-identifying lessons only. No host paths, internal names, model
catalogs or raw session data.

## 2026-10-23 — official profiling and cache documentation review

### Findings

- XProf is the profiling viewer behind the TensorBoard "Profile" tab, not a
  built-in TensorBoard feature. `xprof` must be installed in the viewing
  environment; the standalone viewer is `xprof --port <port> <trace-dir>`.
- A capture without `block_until_ready()` can show dispatch but miss on-device
  execution. The official capture snippet includes it for that reason.
- Current cache options are `jax_compilation_cache_dir`,
  `jax_persistent_cache_min_compile_time_secs`,
  `jax_persistent_cache_min_entry_size_bytes` and
  `jax_persistent_cache_enable_xla_caches`; the XLA-cache value `all` enables
  the extra kernel and autotune caches. They must be set before the first
  compilation.
- The compilation cache is trusted code: a user-only-writable directory is a
  safety requirement, not a performance tune.

### Struggles

- An earlier version pointed only at TensorBoard and left the viewer
  prerequisite implicit, so a reader could capture a trace and find no Profile
  tab.
- The snippet was described in a comment instead of shown, so the `os` import
  and the ordering of start/stop were easy to get wrong.

### Tips

- Run the capture with the same selected interpreter that runs the benchmark;
  record `sys.prefix`, JAX/jaxlib versions and the device type.
- Select the viewing environment explicitly when installing `xprof`; existing
  installation authority applies without a new confirmation step.
- Keep one TensorBoard install to avoid the duplicate-plugins error.
- A trace is evidence of what ran, not proof of a speedup. Measure before and
  after under the same conditions.

### Promotion judgment

- Promoted the viewer prerequisite, the complete capture snippet and the
  failure table to `SKILL.md`.
- Kept the dated documentation URLs and the "no automatic install" boundary
  visible; no GPU execution or performance claim is made by this record.
