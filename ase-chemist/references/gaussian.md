# Gaussian Reference (v1.4 — DFT SP / Opt / Freq) — index

v1.4 ships DFT single-point energy + forces + dipole, geometry
optimization, and frequency / thermochemistry analysis through ASE's
`ase.calculators.gaussian.Gaussian` calculator. All three scripts run
**through ASE** in the standard Calculator pattern — the g16/g09
binary runs as a subprocess managed by ASE's `FileIOCalculator`
machinery, same orchestration model as MACE, tblite, EMT, etc.
**No carve-out, no cclib.** The in-house `_gaussian_log.py` is a
pure-regex helper, not an alternate calculator.

This file is an index. Each topic lives in its own scoped file —
read only the one that matches your task instead of paging through
the whole chapter.

## When to read which file

- [`gaussian_method_selection.md`](gaussian_method_selection.md) —
  the v1.4 framing (what the three scripts ship and the
  through-ASE / no-cclib stance) plus the method-selection rules
  (when to reach for Gaussian vs stay on xTB; DFT functional /
  thermochem / TM / HOMO-LUMO routing).
- [`gaussian_no_defaults.md`](gaussian_no_defaults.md) — the
  no-defaults policy (`--method`, `--basis`, `--charge`,
  `--multiplicity`, `--mem`, `--nproc` all required), defensible
  recommendations to suggest, solvation (SMD vs PCM), and resource
  flags (why no auto-detect under SLURM/cgroups).
- [`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md) — version
  detection, override flag, and practical route-line differences
  between g16 and g09.
- [`gaussian_log_parser.md`](gaussian_log_parser.md) — the in-house
  `_gaussian_log.py` helper (vib_freqs / thermochem / Mulliken /
  HOMO-LUMO), the rationale for not using cclib, and what's
  intentionally not parsed.
- [`gaussian_failure_modes.md`](gaussian_failure_modes.md) — v1.4
  out-of-scope list, known wrong-but-plausible failure modes
  (multiplicity, solvation mismatch, scratch dir, imaginary
  frequencies), and concrete troubleshooting fixes.

The five files together replace the v1.4 monolithic `gaussian.md`
chapter. SKILL.md, scripts/gaussian_*.py, PLAN.md, CLAUDE.md, and
README.md may still cite `references/gaussian.md §1` etc. — this
index keeps those pointers valid by directing the model to the
right sub-file.
