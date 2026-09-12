---
name: jax-performance-tuning
description: Speed up JAX compilation, enable persistent compilation caches, and improve JAX run-time performance on GPU boxes (including Blackwell / cuDNN 9 / multi-GPU). Use when a JAX job recompiles every run, compile takes minutes, steps/samples-per-second are low, GPU utilization is poor, or when asked to profile/tune/cache JAX workloads. Triggers include: JAX コンパイルが遅い, コンパイルキャッシュ, jax_compilation_cache_dir, XLA_FLAGS 最適化, BF16/AMP が効かない, GPU 使用率が低い, jax.profiler, micro-batch 調整.
---

# JAX Performance Tuning (compile cache + runtime)

## When to use

*   JAX recompiles on every process start / every config tweak.
*   Compile time dominates the session; step time looks fine but iterations are slow.
*   GPU utilization is low or memory is small relative to the card.
*   You need BF16/AMP, micro-batch sizing, remat, or profiling evidence.

## Workflow (do in this order)

1.  **Measure before changing** — time one step with `jax.block_until_ready`, and
    check data loading separately (e.g. a `profile_step`-style script).
2.  **Enable the persistent compilation cache** (biggest single win).
    ```bash
    export JAX_COMPILATION_CACHE_DIR=/tmp/opencode/jax_cache
    export JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS=0
    export JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES=-1
    export JAX_PERSISTENT_CACHE_ENABLE_XLA_CACHES=all   # kernel + autotune caches
    ```
    *   Cache is **trusted**: keep it in a user-only-writable directory.
    *   Verify hits with `JAX_LOG_COMPILES=1`.
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
        trace (measured ~2.1× step speedup on a 2-GPU Blackwell box).
    *   **Micro-batch**: increase until memory is ~70–80% used. Measured
        example: micro1 4.83s / micro4 2.96s / micro8 2.66s per step with the
        effective batch held constant.
        Keep the effective batch constant via `lax.scan` gradient accumulation.
    *   `XLA_PYTHON_CLIENT_PREALLOCATE=false` when evaluation runs in the same process.
    *   `jax.checkpoint` (remat) around encoder/decoder when doing multiple
        forward/backward passes (e.g. SAM-style optimizers).
5.  **Diagnose with profiling, not guesses**
    ```bash
    jax.profiler.start_trace("/tmp/opencode/trace"); ... ; jax.profiler.stop_trace()
    # summarize without TensorBoard:
    python scripts/analyze_trace.py /tmp/opencode/trace
    ```
    Look for: tiny-GEMM floods, `convertTensor` dtype kernels (low precision not applied),
    host gaps (dataloader), giant monolithic temp allocations (remat/split needed).
6.  **Host CPU (many-core boxes)**
    *   Data loading: `ThreadPoolExecutor(prefetch=2..4)` around image decode.
    *   `OMP_NUM_THREADS=32` for host BLAS; do not set 256 (compiler thread thrash).
    *   There is **no** GPU compile-parallelism XLA flag in current XLA
        (`xla_gpu_force_compilation_parallelism` does not exist); CPU codegen uses
        `--xla_cpu_parallel_codegen_split_count` (default 32).
    *   When running several jobs, compile one at a time so they share the cache
        (a second job with the same HLO starts instantly).

## GPU stability notes (Blackwell / cuDNN 9)

*   `XLA_FLAGS="--xla_gpu_enable_command_buffer= --xla_gpu_enable_triton_gemm=false"`
    avoids observed illegal-address and `Autotuning failed ... No valid config` failures.
    Command buffers were only ~+3% when enabled.
*   cuDNN sub-libraries need `.venv/.../nvidia/*/lib` on `LD_LIBRARY_PATH`
    **before interpreter start** (glibc caches it). Re-exec once from Python if missing.
*   Beware monolithic executable temp memory: XLA may report a 16–33 GiB single
    allocation. Reduce with remat, micro-batch, and lighter decoder shapes.

## Optional advanced

*   `JAX_ENABLE_PGLE=yes` + `JAX_PGLE_PROFILING_RUNS=3` (profile-guided latency
    estimator, needs persistent cache; mostly for multi-GPU collectives).
*   `JAX_OPTIMIZATION_LEVEL=O1` (runtime speed at compile-time cost; cache it).
*   Buffer donation: needs optimizer state not to alias params
    (`z = tree_map(jnp.array, params)` first).

## References

*   https://docs.jax.dev/en/latest/persistent_compilation_cache.html
*   https://docs.jax.dev/en/latest/xla_flags.html
*   https://github.com/jax-ml/jax/discussions/3732  (Python loops vs `lax.scan`)
*   https://docs.jax.dev/en/latest/gpu_performance_tips.html  (PGLE)
*   https://github.com/openxla/xla/blob/main/xla/debug_options_flags.cc  (flag list)
*   See the target project's own performance notes for environment-specific values.
