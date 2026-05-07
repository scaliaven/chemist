# Gaussian out-of-scope + known failure modes + troubleshooting

Part of the v1.4 Gaussian reference set. Companion files:
[`gaussian_method_selection.md`](gaussian_method_selection.md),
[`gaussian_no_defaults.md`](gaussian_no_defaults.md),
[`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md),
[`gaussian_log_parser.md`](gaussian_log_parser.md). Index:
[`gaussian.md`](gaussian.md).

## Out of scope (v1.4)

These are not in v1.4 and are intentionally not blocking issues:

- **Transition-state searches** (`Opt=TS`, QST2/QST3) and **IRC**
  (`IRC=...`). TS needs a good Hessian guess (`CalcFC`/`ReadFC`) and
  IRC verification — neither fits the "skill writes a script, user
  runs it" pattern. Push to v3+.
- **Anharmonic frequencies** (`Freq=Anharmonic`). Expensive and needs
  careful normal-mode follow-up.
- **NBO analysis** (`Pop=NBO`) and **NPA charges**. NBO output has
  a different format that's not worth a parser for v1.4; v3
  candidate.
- **Post-Hartree-Fock correlated methods** (CCSD, CCSD(T), MP2,
  CASSCF). Method-specific basis-set / memory / disk heuristics.
- **Excited-state methods** (TDDFT, CIS, EOM-CCSD).
- **Resource autodetection** — see [`gaussian_no_defaults.md`](gaussian_no_defaults.md).
- **Local-vs-queue submission** — v1.4 runs locally only. SLURM
  templates may land in v2.5+; for now the user wraps the script in
  their own queue script.

## Known failure modes

- **Wrong multiplicity → silently converged-but-wrong wavefunction**
  for some open-shell systems. If energies look weird, double-check
  `--multiplicity`.
- **Solvation mismatch across chain** — SP gas phase, Opt solvated,
  Freq gas phase produces garbage thermochem. The scripts don't
  enforce consistency; surface this to the user.
- **GAUSS_SCRDIR unset** — Gaussian writes scratch to its default
  location, often `/tmp` or `/scratch` with small quotas. `check_env.py`
  flags this; tell users to set it before non-trivial runs.
- **Imaginary frequencies in `gaussian_freq.py`** — typically the
  preceding optimization wasn't tight enough. Re-optimize at
  `--convergence tight` or `verytight` and re-run.
- **g16 vs g09 route differences** — see [`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md). If a route line copied
  from older docs fails on g16, try removing redundant
  `SCF=Tight` first.

## Troubleshooting

- **"Unknown keyword" / "Syntax error in route"** — usually a typo or
  a g09-specific keyword on g16 (or vice versa). Check the .com file
  written by ASE under `<label>.com`; route line is on the line
  starting with `#P`.
- **Job runs but the parser returns empty / None** — usually means
  Gaussian errored partway. Look at `<label>.log` for `Error
  termination`. The in-house parser fails silently rather than
  raising, so you have to inspect the log directly.
- **Out of disk** — Gaussian scratch fills up. Set `GAUSS_SCRDIR` to
  a fast, large-quota path before the run.
- **`%mem` insufficient** — Gaussian writes "Out-of-memory error in
  routine ..." to the .log. Re-run with a bigger `--mem`.
- **SCF doesn't converge** — try `SCF=(MaxCycle=200,XQC)` via
  `--extra-route`. If it still fails, the geometry is probably
  pathological.
