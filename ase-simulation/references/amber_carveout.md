# Amber architectural carve-out (v1.3)

Part of the v1.3 Amber reference set. Companion files:
[`amber_method_selection.md`](amber_method_selection.md),
[`amber_pipeline.md`](amber_pipeline.md),
[`amber_force_fields.md`](amber_force_fields.md),
[`amber_failure_modes.md`](amber_failure_modes.md). Index:
[`amber.md`](amber.md).

> **⚠️ Architectural carve-out.** Amber is **the only engine in
> `ase-simulation` that does not run through ASE.** Every other backend
> in the skill (EMT, LJ, TIP3P, tblite/xTB, MACE) is wrapped as an ASE
> `Calculator` and driven by ASE optimizers / MD integrators in-process.
> Amber bypasses all of that: `parameterize_gaff2.py` and `run_amber.py`
> shell out to AmberTools binaries (`antechamber`, `parmchk2`, `tleap`)
> and Amber MD engines (`pmemd.cuda` / `pmemd` / `sander`) via
> `subprocess.run`. The MD integration loop runs **natively in pmemd**;
> ASE only sees the input structure on the way in and the NetCDF `.nc`
> trajectory on the way out (handed to `analyze_traj.py` for analysis).
>
> **The carve-out was a performance choice, not forced.** `ase.
> calculators.amber` actually ships **two** classes:
>
> 1. `Amber` (FileIOCalculator) — shells out to `sander -O` once per
>    `calculate()` call. Single E/F per subprocess. **This** is what's
>    unusable as an MD integrator: ASE's `Langevin` would re-launch
>    sander every fs, and subprocess startup × N steps dwarfs the
>    physics. This class also rejects non-orthogonal cells (the box-
>    truncated-octahedron problem). Use it for one-off SP only.
> 2. `SANDER` (Calculator) — uses the **`pysander` Python bindings**
>    in-process. `sander.setup(...)` once at construction, then
>    `sander.energy_forces()` per `calculate()` call — pure Python
>    function calls into a C extension, no subprocess per step. ASE's
>    `Langevin` / `VelocityVerlet` would drive this cleanly. The box
>    is taken from `crd.box` directly, so the orthogonal-cell
>    restriction does **not** apply.
>
> The `SANDER` path is a viable in-process Amber-via-ASE option. v1.3
> declined it for three concrete reasons:
>
> - **Engine.** `pysander` binds to **sander** (the reference engine),
>   not pmemd. On a typical 5k-atom system, sander runs at ~1–10 ns/day
>   (CPU); pmemd.cuda runs at ~100–300 ns/day on an A100. The whole
>   "min → heat → density → 500 ps prod" protocol is hours via SANDER
>   vs. minutes via pmemd.cuda.
> - **No GPU.** `pysander` has no GPU bindings; `pmemd.cuda` cannot be
>   driven from Python this way.
> - **Maturity.** ASE's docs carry a "tested only for amber16"
>   disclaimer for the Amber module; pmemd direct shell-out has no
>   such caveat and is the production-tested path.
>
> The trade is real either way. The shell-out path costs architectural
> coherence; the SANDER path costs production throughput. v1.3 picked
> speed; that decision is **not** load-bearing and is reviewable.
>
> **The v1.3 Amber path is under review.** Four open options:
>
> 1. **Keep pmemd shell-out** (current). Carve-out documented;
>    production-fast.
> 2. **Switch to `SANDER` + ASE Langevin**. Architecturally clean;
>    accepts CPU-only and ~10–50× slower throughput.
> 3. **Remove Amber entirely** and tell users honestly that the skill
>    doesn't ship a classical MM backend.
> 4. **Build the missing API path** — write a proper ASE Calculator
>    that wraps `pmemd` / `pmemd.cuda` directly. Two sub-shapes are
>    plausible: (a) a long-lived `pmemd` subprocess where ASE owns
>    setup/teardown but pmemd owns the integration loop (preserves
>    pmemd.cuda speed and brings the wrapper into ASE-Calculator
>    shape at the script level, even if per-step E/F isn't exposed);
>    (b) contribute `pmemd`/`pmemd.cuda` Python bindings upstream so
>    a future `PMEMD` class in `ase.calculators.amber` can bind them
>    the way `SANDER` binds pysander. Most work of the four options;
>    only one with both ASE-coherence and pmemd.cuda throughput.
>
> See [`PLAN.md`](../../PLAN.md) §"Phase 3" for the decision criterion
> (usage frequency × GPU prevalence × engineering capacity).
