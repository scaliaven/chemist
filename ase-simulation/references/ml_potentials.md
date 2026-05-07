# ML Potentials Reference (v1.2 — MACE-MP-0 + MACE-OFF) — index

v1.2 ships **MACE-MP-0** (89-element materials foundation model) and
**MACE-OFF** (10-element organics foundation model) as supported ASE
Calculators, both via `pip install mace-torch`. The framing: ML
potentials are an **accelerator on top of trusted methods, not a
replacement.**

This file is an index. Each topic lives in its own scoped file —
read only the one that matches your task instead of paging through
the whole chapter.

## When to read which file

- [`ml_method_selection.md`](ml_method_selection.md) — when to reach
  for MACE vs stay with xTB; element-set routing (MACE-OFF for
  organics, MACE-MP-0 for materials); how the bundled scripts wire it.
- [`ml_validation_contract.md`](ml_validation_contract.md) — the
  mandatory cross-validation contract (1 ps cadence vs GFN2-xTB,
  abort at MAE_F > 100 meV/Å). Read this before disabling validation.
- [`ml_failure_modes.md`](ml_failure_modes.md) — known wrong-but-
  plausible cases (liquid mixtures, OOD geometries, size cliff,
  reactive chemistry, hard-element edges); GPU/CPU notes.
- [`ml_troubleshooting.md`](ml_troubleshooting.md) — concrete fixes
  (CUDA OOM, weight-download hangs, immediate MAE_F blowup); v1.2
  out-of-scope and v2.2+ planned additions.

The four files together replace the v1.2 monolithic
`ml_potentials.md` chapter. SKILL.md cross-references and other
documents may still cite `ml_potentials.md` — this index keeps those
pointers valid.
