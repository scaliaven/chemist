# ML Potentials Reference (v1.2 — MACE-MP-0 + MACE-OFF)

This file replaces the v2 stub. v1.2 ships **MACE-MP-0** (89-element
materials foundation model) and **MACE-OFF** (10-element organics
foundation model) as supported ASE Calculators, both via
`pip install mace-torch`. The framing remains: ML potentials are an
**accelerator on top of trusted methods, not a replacement.** The
cross-validation contract (§2) is what makes that statement honest;
do not turn it off without a specific reason.

## §1. Method-selection rules

The MACE branch is for **systems where GFN2-xTB is too slow**, not for
systems where GFN2-xTB is fine. Use these in order:

1. **System has < ~500 atoms** → use GFN2-xTB. Faster than MACE on CPU,
   no model-weights download, no validation overhead, fully trusted.
2. **System has ~500–1000 atoms and the task is dynamics** → use
   GFN2-xTB if the run is short (~10 ps), MACE if the run is long
   (>~50 ps). xTB scales O(N³) so the wall-clock crossover is duration-
   sensitive.
3. **System has > ~1000 atoms** → use MACE. Routing:
   - All elements ∈ {H, C, N, O, P, S, F, Cl, Br, I} → **MACE-OFF**
     (the organics foundation model; outperforms GFN2-xTB on torsions
     and conformers).
   - Otherwise → **MACE-MP-0** (the materials foundation model;
     covers 89 elements, MPTrj+sAlex training).
   - Override with `--mace-system-class organic` or `materials` if you
     want to force a specific model (e.g., a metal–organic framework
     where the auto-rule picks MACE-MP-0 but you'd rather use
     MACE-OFF on the organic ligands separately).
4. **System has > ~2000 atoms (40 GB GPU) or > ~1000 atoms (CPU)** →
   you're past the practical MACE-medium ceiling. Drop to
   `--mace-size small` first; if that still OOMs, shrink the system
   or wait for v2.2's CHGNet/Orb integration.

The skill's bundled scripts wire this in:
- `scripts/optimize.py --calculator mace [--mace-system-class ...]
  [--mace-size small|medium|large]`
- `scripts/run_md.py --calculator mace [...]`

## §2. Cross-validation contract

ML potentials produce plausible-looking energies and forces that can be
**wrong in ways the user does not notice**. The skill's load-bearing
defense against that is mandatory cross-validation against GFN2-xTB:

- **`run_md.py` validates by default** when `--calculator mace` is
  used. Every `--validate-every` ps (default `1.0`) it copies the live
  `atoms`, attaches `tblite`'s GFN2-xTB calculator, recomputes
  energy + forces, and writes a row to `validation.csv`:
  ```
  step,MAE_E_meV,MAE_F_meV_per_A,max_F_dev_meV_per_A
  ```
- **The MD aborts** when `MAE_F > --abort-mae-f` meV/Å (default 100 —
  the published rule of thumb for "trajectory drifted out of training
  distribution"). On abort, the script prints the breach step, flushes
  the CSV, and exits with code 3. Trust the trajectory only up to the
  step preceding the breach.
- **Opt-out is available but not the default.** `--no-validate`
  disables validation for that run; use it only when (a) the run is
  short enough that you don't care, or (b) you've already validated a
  representative window and are extending it. Do not opt out as a
  matter of habit.
- **Post-hoc validation** of a saved trajectory uses
  `scripts/validate_ml_md.py --trajectory md.traj`. Same threshold,
  same CSV format. Use it when you ran with `--no-validate` and now
  want to check, or when you want to re-validate at a finer stride.

This contract is the basis on which the skill recommends MACE at all.
If the user asks to disable it permanently, that's a real conversation
about their use case (validation-rich exploratory runs vs. production
where xTB is unaffordable), not a flag flip.

## §3. Known failure modes

These are documented limits where MACE produces wrong but plausible
output. Tell the user before they hit them, not after.

- **Liquid mixtures (ethanol-water etc.).** MACE-MP-0 has documented
  qualitative density and structure errors on aqueous mixtures
  (Rowan analyses, 2024). For mixtures use TIP3P + classical force
  fields where available, or accept that MACE is exploratory only.
- **Out-of-distribution geometries** during MD. The cross-validation
  contract is the primary defense; a fast-rising MAE_F is the abort
  signal. If validation shows MAE_F climbing without breaching, the
  trajectory is still flagged — examine `validation.csv` before
  trusting downstream analysis.
- **Hard-element edge cases.** MACE-MP-0 covers 89 elements but
  performance is best on the MPTrj-trained subset. Lanthanides,
  actinides, and exotic main-group oxidation states get weaker
  forces. Cross-check against a published phonon or formation-
  energy benchmark for the element class.
- **Practical size cliff.** Medium MACE on a 40 GB GPU runs out of
  VRAM around 1–2k atoms; CPU mode roughly halves that ceiling.
  `check_env.py` prints free VRAM so the size warning is grounded
  in your actual box.
- **Reactive chemistry.** MACE foundation models are trained on
  near-equilibrium configurations. Bond-breaking / bond-forming
  events (single-step reactions, transition states) are out of
  distribution and will produce silent garbage. Use GFN2-xTB or
  DFT for those — and run cross-validation if you must use MACE.

## §4. GPU/CPU notes

- `check_env.py` reports `torch.cuda.is_available()` and free VRAM.
  When CUDA is unavailable, `make_ml_calc` falls back to CPU and
  prints a one-line warning. Production runs on CPU are workable
  but ~10× slower than GPU; the size cliff drops to ~500–1000 atoms.
- `--mace-device cuda|cpu` overrides auto-detection. Useful for
  debugging (force CPU to avoid OOM diagnostics) or for shared GPU
  systems where you want to be explicit.
- `--mace-size small|medium|large` trades speed for accuracy.
  Default `medium` is the published "first to reach for"; drop to
  `small` only if OOM is unavoidable.
- Model weights are downloaded **on first use** (HuggingFace Hub
  under the hood). The download is multi-hundred-MB; it is cached
  per-user and not redone. `check_env.py` does not download weights
  to keep environment checks fast.

## §5. Troubleshooting

- **`OutOfMemoryError` from CUDA.** Drop `--mace-size` to `small`,
  or shrink the system. If the system is rigid (a crystal), reducing
  the supercell often gets you under the ceiling without changing the
  physics. As a last resort, `--mace-device cpu` accepts the
  slowdown for an OOM-free run.
- **Weights download fails or hangs.** Hugging Face Hub access can be
  blocked on some HPC nodes. Download MACE weights on a login node,
  then point `mace-torch` at the cached path (env var `HF_HOME`).
- **`MAE_F` blows up immediately** (frame 0 or frame 1). Three usual
  causes: (a) wrong-element routing — check that MACE-OFF was picked
  for an organic system; (b) wrong charge/multiplicity; (c) the
  reference (xTB) is itself failing — re-run with `--calculator xtb`
  alone to confirm xTB converges.
- **Validation makes the run too slow.** Increase `--validate-every`
  (default 1.0 ps; try 5.0 for slow-changing systems). Do not set
  `--no-validate` as the first move.

## §6. Out of scope (explicitly, even in v1.2)

These are not in v1.2 and are not blocking issues — they are research
or scope decisions:

- **Training new ML potentials.** Research workflow with its own
  dataset/loss/hyperparameter ecosystem; does not belong in a
  simulation-orchestration skill.
- **Fine-tuning foundation models** (MACE-MP-0, MACE-OFF, Orb,
  CHGNet) on user data. Same reasoning.
- **Active-learning loops** that alternate ML inference with reference
  DFT calls and retrain.
- **Equivariant / message-passing internals.** v1.2 uses MACE as a
  black-box ASE calculator. Anyone who needs to peek inside should
  read the package docs directly.

Future v2.2+ adds (gated on usage data):

- **CHGNet** for charge-aware materials (battery cathodes,
  oxidation-state-sensitive systems).
- **Orb-v3** with its built-in confidence head (per-atom binned
  force-error predictions) for richer OOD signal than committee
  uncertainty alone.
- **Committee-uncertainty heads** on a frozen MACE-MP-0 backbone,
  per the multi-head committee work (JCP 2025; arXiv 2508.09907).
