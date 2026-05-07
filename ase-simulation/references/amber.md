# Amber Reference (v1.3 — GAFF2 small-molecule MD) — index

v1.3 ships **GAFF2 + AM1-BCC** small-molecule explicit-solvent MD via
two scripts (`scripts/parameterize_gaff2.py`, `scripts/run_amber.py`)
that shell out to AmberTools (`antechamber`, `parmchk2`, `tleap`) and
Amber MD engines (`pmemd.cuda` > `pmemd` > `sander`). Amber is the
**only engine in `ase-simulation` that does not run through ASE** —
the architectural carve-out and its review options are documented in
[`amber_carveout.md`](amber_carveout.md). Protein and nucleic-acid MD
(ff19SB+OPC, OL21) are deferred to **v2.3**.

This file is an index. Each topic lives in its own scoped file —
read only the one that matches your task instead of paging through
the whole chapter.

## When to read which file

- [`amber_carveout.md`](amber_carveout.md) — the architectural
  carve-out warning: why Amber bypasses ASE, the `Amber` vs `SANDER`
  ASE classes, and the four open options for the v1.3 path under
  review. Read this when GAFF2 is recommended or when questioning
  why Amber doesn't go through ASE like every other backend.
- [`amber_method_selection.md`](amber_method_selection.md) — the
  5-rule walk for when to reach for GAFF2 vs GFN2-xTB vs "not yet
  supported"; v1.3-ships framing and the protein/NA-deferred-to-v2.3
  note. Cited as "references/amber.md §1" by scripts and SKILL.md.
- [`amber_pipeline.md`](amber_pipeline.md) — the two-script bash
  pipeline (`parameterize_gaff2.py` → `run_amber.py` →
  `analyze_traj.py`) plus idempotency notes.
- [`amber_force_fields.md`](amber_force_fields.md) — force-field
  choices (GAFF2, GAFF, RESP), water models (TIP3P, OPC, others),
  charge assignment (AM1-BCC, RESP, the mandatory `--net-charge`
  flag), and engine selection (`pmemd.cuda` > `pmemd` > `sander`).
- [`amber_failure_modes.md`](amber_failure_modes.md) — known
  failure modes (antechamber aromatic perception, wrong
  `--net-charge`, box-too-small, octahedron not used, CPU-only
  engine mismatch, `pmemd.cuda` OOM); troubleshooting recipes; and
  the v1.3 out-of-scope list (proteins, free energy, REMD, QM/MM,
  umbrella sampling, constant-pH, anisotropic barostat, SLURM).

The five files together replace the v1.3 monolithic `amber.md`
chapter. SKILL.md, PLAN.md, CLAUDE.md, `scripts/parameterize_gaff2.py`,
and `scripts/run_amber.py` may still cite `amber.md` (e.g.,
"references/amber.md §1") — this index keeps those pointers valid by
directing the model to the right sub-file.
