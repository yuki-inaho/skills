---
name: jax-performance-tuning
description: 'Speed up JAX compilation, enable persistent compilation caches, and improve JAX run-time performance on GPU boxes (including Blackwell / cuDNN 9 / multi-GPU). Use when a JAX job recompiles every run, compile takes minutes, steps/samples-per-second are low, GPU utilization is poor, or when asked to profile/tune/cache JAX workloads. Triggers include: JAX コンパイルが遅い, コンパイルキャッシュ, jax_compilation_cache_dir, XLA_FLAGS 最適化, BF16/AMP が効かない, GPU 使用率が低い, jax.profiler, micro-batch 調整.'
---

# JAX Performance Tuning (compile cache + runtime)

## When to use

*   JAX recompiles on every process start / every config tweak.
*   Compile time dominates the session; step time looks fine but iterations are slow.
*   GPU utilization is low or memory is small relative to the card.
*   You need BF16/AMP, micro-batch sizing, remat, or profiling evidence.

## Prerequisites

*   Use the selected environment for both the benchmark and the capture — the
    interpreter that imports the JAX/jaxlib you are measuring, not a global
    interpreter. Record `sys.prefix`, the JAX/jaxlib versions, the command and
    the device type beside any measurement.
*   The profile viewer is **XProf**, which supplies the TensorBoard "Profile"
    tab; `xprof` must be installed in the viewing environment alongside
    TensorBoard. Select the viewing environment explicitly; for example,
    `pip install xprof` in that environment. Existing installation authority
    applies; this skill adds no confirmation step and
    makes no GPU-execution or GPU-performance claim.
*   Keep one TensorBoard install. Multiple TensorBoard/TensorFlow packages cause
    the "duplicate plugins" startup error described in the official guide.
*   A compilation cache is trusted: keep it in a directory only the run user can
    write.

## Procedure

Do these in this order.

1.  **Measure before changing** — time one step with `jax.block_until_ready`, and
    check data loading separately (e.g. a `profile_step`-style script).
2.  **Enable the persistent compilation cache** (usually the highest-leverage change; verify on your workload).
    ```bash
    export JAX_CACHE_DIR="${JAX_CACHE_DIR:?set JAX_CACHE_DIR to a user-only-writable directory}"
    export JAX_COMPILATION_CACHE_DIR="$JAX_CACHE_DIR/compilation"
    export JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS=0
    export JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES=-1
    export JAX_PERSISTENT_CACHE_ENABLE_XLA_CACHES=all   # kernel + autotune caches
    ```
    *   Cache is **trusted**: keep it in a user-only-writable directory.
    *   The same options are available as
        `jax.config.update("jax_compilation_cache_dir", ...)` and the matching
        `jax_persistent_cache_*` config names, set before the first compilation.
        Official `jax_persistent_cache_enable_xla_caches` values are `all`,
        `none`, `xla_gpu_kernel_cache_file`, and the default
        `xla_gpu_per_fusion_autotune_cache_dir`.
    *   Inspect persistent-cache diagnostics with
        `JAX_DEBUG_LOG_MODULES=jax._src.compiler,jax._src.lru_cache` before
        launch; compilation logs alone do not prove a cache hit.
        `jax.config.update("jax_explain_cache_misses", True)` can explain
        tracing misses; its coverage is version-dependent.
    *   Prefer `jit(f).lower(*example_args).compile()` (AOT) so epoch-boundary
        compiles cannot kill a long run.
3.  **Remove compile-time hazards in the code**
    *   No Python `for` loops over batch/steps → use `jax.lax.scan` / `lax.map` / `jax.vmap`.
    *   Keep shapes and static config fixed; changing constants (e.g. `total_steps`,
        warmup) creates a new executable. Run benchmarks with the production values
        so the cache is shared.
    *   One fat `jax.jit` per training step beats many small jit calls.
4.  **Runtime speed (typical order of impact)**
    *   **Actually enable low precision**: if the framework provides a
        compute-precision context (e.g. a `compute_precision("bf16")` helper),
        wrap the loss/forward path at trace time; otherwise ops silently run
        fp32/TF32 with extra dtype-convert kernels. Verify with a profiler
        trace; record the hardware, JAX/XLA version, command and date next to
        any speedup you report.
    *   **Micro-batch**: increase until memory is ~70–80% used. Measure the
        step time and record the exact micro-batch values; there is no portable
        speedup number.
        Keep the effective batch constant via `lax.scan` gradient accumulation.
    *   `XLA_PYTHON_CLIENT_PREALLOCATE=false` when evaluation runs in the same process.
    *   `jax.checkpoint` (remat) around encoder/decoder when doing multiple
        forward/backward passes (e.g. SAM-style optimizers).
5.  **Diagnose with profiling, not guesses**
    Confirm the viewer prerequisite above, then capture the workload actually
    under test. Keep `block_until_ready()`: JAX dispatches asynchronously, and
    without it the trace can miss on-device execution.

    ```python
    import os

    import jax
    import jax.numpy as jnp

    trace_dir = os.environ["JAX_TRACE_DIR"]  # user-provided, outside the repo
    os.makedirs(trace_dir, exist_ok=True)

    @jax.jit
    def step(x):
        return x @ x

    x = jnp.ones((1024, 1024), dtype=jnp.float32)  # replace with the workload

    jax.profiler.start_trace(trace_dir)
    y = step(x)            # run the workload being measured
    y.block_until_ready()  # include device execution, not just dispatch
    jax.profiler.stop_trace()
    ```

    ```bash
    export JAX_TRACE_DIR="${JAX_TRACE_DIR:?set JAX_TRACE_DIR to a user-provided directory}"
    tensorboard --logdir "$JAX_TRACE_DIR"   # "Profile" tab requires xprof
    xprof --port 8791 "$JAX_TRACE_DIR"      # standalone XProf viewer
    ```

    Both viewers read the same trace directory; `start_trace` must point at it.
    The official guide is
    https://docs.jax.dev/en/latest/201/profiling.html (XProf). A trace shows
    what ran and where time went; it is not a speedup claim by itself, and this
    skill does not claim GPU execution or GPU performance.

    Look for: tiny-GEMM floods, `convertTensor` dtype kernels (low precision not applied),
    host gaps (dataloader), giant monolithic temp allocations (remat/split needed).
6.  **Host CPU (many-core boxes)**
    *   Data loading: `ThreadPoolExecutor(prefetch=2..4)` around image decode.
    *   `OMP_NUM_THREADS=32` for host BLAS; do not set 256 (compiler thread thrash).
    *   There is **no** GPU compile-parallelism XLA flag in current XLA
        (`xla_gpu_force_compilation_parallelism` does not exist); CPU codegen uses
        `--xla_cpu_parallel_codegen_split_count` (default 32).
    *   When running several jobs, compile one at a time so they share the cache
        (a second job with the same HLO can reuse the cached compilation).

## GPU stability notes (Blackwell / cuDNN 9)

*   `XLA_FLAGS="--xla_gpu_enable_command_buffer= --xla_gpu_enable_triton_gemm=false"`
    is a workaround to evaluate when illegal-address or `Autotuning failed ... No
    valid config` failures are observed. Measure any command-buffer effect on the
    target stack; do not assume a gain.
*   cuDNN sub-libraries need `.venv/.../nvidia/*/lib` on `LD_LIBRARY_PATH`
    **before interpreter start** (glibc caches it). Re-exec once from Python if missing.
*   Beware monolithic executable temp memory: XLA may report a single large
    allocation. Record the actual size and reduce it with remat, micro-batch, and
    lighter decoder shapes.

## Optional advanced

*   `JAX_ENABLE_PGLE=yes` + `JAX_PGLE_PROFILING_RUNS=3` (profile-guided latency
    estimator, needs persistent cache; mostly for multi-GPU collectives).
*   `JAX_OPTIMIZATION_LEVEL=O1` (runtime speed at compile-time cost; cache it).
*   Buffer donation: needs optimizer state not to alias params
    (`z = tree_map(jnp.array, params)` first).

## Verification

- A before/after comparison uses the same workload, dtype, batch, device,
  JAX/jaxlib versions and XLA flags. Report the command, versions, device and
  date with the number.
- Use `JAX_LOG_COMPILES=1` for compilation logs. For persistent-cache activity,
  set `JAX_DEBUG_LOG_MODULES=jax._src.compiler,jax._src.lru_cache` before launch
  and inspect the cache diagnostics across identical runs. Compilation logs alone
  do not prove a persistent-cache hit; a hit is not a speedup claim.
- The trace directory contains the `start_trace`/`stop_trace` output, and the
  viewer shows the expected device timeline rather than only host events.
- The cache directory is user-only-writable and was set before the first
  compilation.

## Failure handling

| Symptom | Cause | Action |
| --- | --- | --- |
| TensorBoard starts with a duplicate-plugins error | More than one TensorBoard/TensorFlow package is installed | Uninstall the duplicates and reinstall one `tensorboard` plus `xprof`; do not add another profiler plugin |
| No "Profile" tab, or `xprof` is not found | `xprof` is missing from the viewing environment | Make `xprof` available in the selected viewing environment; verify the viewer before capturing again |
| Trace contains host events but no device timeline | The workload returned before device work finished | Add `block_until_ready()` around the measured output and recapture |
| Cache never hits across two identical runs | Cache directory was set after first compilation, or jaxlib/flags/device topology changed | Set the cache before the first compile and compare the recorded versions/conditions; a cache hit is not a speedup claim |
| Illegal address or autotuning failure on a new GPU stack | Stack-specific stability issue | Test the documented XLA workaround in the GPU stability section and measure it; do not assume it helps |

Do not report a change as a speedup without a same-condition measurement.
Record the command, versions, device and date with any number you report.

## Growth log

Dated, generic lessons live in [references/growth-log.md](references/growth-log.md).
Promote a lesson here only after it repeats or is a hard failure mode.

## References

*   https://docs.jax.dev/en/latest/501/compilation-cache.html
    (persistent cache options and thresholds)
*   https://docs.jax.dev/en/latest/201/profiling.html
    (benchmarking, XProf capture and viewer)
*   https://openxla.org/xprof  (standalone XProf and its analysis tools)
*   https://docs.jax.dev/en/latest/xla_flags.html
*   https://github.com/jax-ml/jax/discussions/3732  (Python loops vs `lax.scan`)
*   https://docs.jax.dev/en/latest/gpu_performance_tips.html  (PGLE)
*   https://github.com/openxla/xla/blob/main/xla/debug_options_flags.cc  (flag list)
*   See the target project's own performance notes for environment-specific values.
