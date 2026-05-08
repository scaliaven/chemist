# Gaussian Reference (v1.4 — DFT SP / Opt / Freq) — method selection

Part of the v1.4 Gaussian reference set. Companion files:
[`gaussian_no_defaults.md`](gaussian_no_defaults.md),
[`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md),
[`gaussian_log_parser.md`](gaussian_log_parser.md),
[`gaussian_failure_modes.md`](gaussian_failure_modes.md). Index:
[`gaussian.md`](gaussian.md).

This file replaces the v2 stub. v1.4 ships:

- `scripts/gaussian_sp.py` — DFT single-point energy + forces + dipole
  via `ase.calculators.gaussian.Gaussian`. Mulliken charges and
  HOMO/LUMO eigenvalues parsed by an in-house regex helper
  (`scripts/_gaussian_log.py`).
- `scripts/gaussian_opt.py` — DFT geometry optimization via
  `GaussianOptimizer` (delegates to Gaussian's L103 internal optimizer
  in one g16/g09 invocation, ~10–100× faster than wrapping ASE BFGS
  around per-step Gaussian SP calls).
- `scripts/gaussian_freq.py` — DFT frequency + thermochemistry
  (vib_freqs / ZPE / enthalpy / Gibbs G), parsed by the in-house
  `_gaussian_log.py` helper. **No cclib dependency.** ASE's
  `read_gaussian_out` does not parse vibrational frequencies, so the
  helper fills that gap with ~100 lines of regex against Gaussian's
  format-stable output. Self-contained; no third-party parser needed.

All three scripts run **through ASE** in the standard Calculator pattern
(`atoms.calc = Gaussian(...)`, `atoms.get_potential_energy()` /
`GaussianOptimizer(atoms, calc).run(...)`). The g16/g09 binary runs as
a subprocess managed by ASE's `FileIOCalculator` machinery — same
orchestration model as MACE, tblite, EMT, etc. **No carve-out, no
cclib.** The in-house `_gaussian_log.py` is a pure-regex helper, not
an alternate calculator.

## Method-selection rules

Apply in order. The first rule that fits is your answer.

1. **The user explicitly named a DFT method** (B3LYP, ωB97X-D, M06-2X,
   PBE0, ...) or asked for DFT/CCSD/post-HF accuracy → use Gaussian.
2. **The user wants quantitative thermochemistry** (ZPE, enthalpy,
   Gibbs free energy at ~few-kcal/mol accuracy) → optimize with
   `gaussian_opt.py --convergence tight`, then run `gaussian_freq.py`
   at the same method/basis.
3. **The system is a transition-metal complex and GFN1/GFN2-xTB
   underperformed** → use Gaussian with a TM-appropriate functional
   (PBE0-D3(BJ) or TPSSh-D3 with def2-TZVP).
4. **The user wants HOMO/LUMO at DFT level** rather than the raw xTB
   eigenvalue gap → use `gaussian_sp.py`. The in-house `_gaussian_log.py`
   helper parses MO eigenvalues from the .log and reports eV directly.
   Add `Pop=Reg` via `--extra-route` if Gaussian truncates the default
   eigenvalue list.
5. **Otherwise stay on xTB.** Gaussian jobs cost minutes-to-hours;
   `single_point.py --calculator xtb` costs seconds. The skill should
   recommend Gaussian only when DFT is actually needed, not as a
   default upgrade.
