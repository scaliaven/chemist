# MACE cross-validation contract

Part of the v1.2 ML-potentials reference set. Companion files:
[`ml_method_selection.md`](ml_method_selection.md),
[`ml_failure_modes.md`](ml_failure_modes.md),
[`ml_troubleshooting.md`](ml_troubleshooting.md). Index:
[`ml_potentials.md`](ml_potentials.md).

ML potentials produce plausible-looking energies and forces that can be
**wrong in ways the user does not notice**. The skill's load-bearing
defense against that is mandatory cross-validation against GFN2-xTB.

## How it works

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

## Why this is non-negotiable

This contract is the basis on which the skill recommends MACE at all.
If the user asks to disable it permanently, that's a real conversation
about their use case (validation-rich exploratory runs vs. production
where xTB is unaffordable), not a flag flip.
