# Amber force fields, water models, and engine selection (v1.3)

Part of the v1.3 Amber reference set. Companion files:
[`amber_carveout.md`](amber_carveout.md),
[`amber_method_selection.md`](amber_method_selection.md),
[`amber_pipeline.md`](amber_pipeline.md),
[`amber_failure_modes.md`](amber_failure_modes.md). Index:
[`amber.md`](amber.md).

## Force fields and water models

### Force fields

- **GAFF2** is the default and the only thing v1.3 supports for small
  molecules. It's the post-2020 successor to GAFF, calibrated on a
  larger ZINC-derived dataset, with revised dihedral parameters that
  produce more reliable conformer ensembles.
- **GAFF (the original)** stays usable if the user is reproducing
  literature that explicitly used it. Pass `-at gaff` to antechamber
  manually; v1.3's `parameterize_gaff2.py` does not expose the flag
  (intentional — not the documented default in 2026).
- **GAFF2 + RESP** is more accurate for charged species but needs an
  explicit Gaussian or psi4 single-point. Out of scope for v1.3;
  AM1-BCC is good enough for ~98% of the GAFF2 calibration set.

### Water models

- **TIP3P** is GAFF2's calibration target — pair them. This is the
  v1.3 default.
- **OPC** is a more accurate 4-site water model; pairs naturally with
  ff19SB (proteins) but is fine with GAFF2 too. Pass `--water opc` if
  the user explicitly wants OPC; otherwise stay on TIP3P.
- **TIP4P-Ew, SPC/E, etc.** — supported by tleap but not exposed by
  the v1.3 CLI. Edit `tleap.in` by hand if you need one of these and
  re-run `tleap` directly; the rest of `run_amber.py` will work.

### Charge assignment

- **AM1-BCC via `antechamber -c bcc`** is the v1.3 default. Fast
  (semi-empirical), well-calibrated for GAFF2.
- **RESP via Gaussian + RED-Server** is more accurate but multi-step,
  license-gated (Gaussian), and does not belong in a one-shot CLI.
  Out of scope for v1.3.
- **The `--net-charge` flag is mandatory** — antechamber silently
  uses 0 if you don't pass it, which gives wrong AM1-BCC partial
  charges for any non-neutral species. Always tell the user to
  double-check the formal charge of their molecule.

## Engine selection

`run_amber.py` picks engines in this order, taking the first one on
PATH:

1. **`pmemd.cuda`** — GPU production. AmberTools25 ships it open-
   source; older Amber required a paid license (no longer relevant).
   Roughly 50–200× faster than sander for typical small-molecule
   systems on a single A100.
2. **`pmemd`** — multi-threaded CPU production. Use when no GPU
   available; 5–20× faster than sander.
3. **`sander`** — reference engine. Slow but bulletproof; useful for
   minimization (where the speed difference is small) and for any
   diagnostic step where you want the documented reference behaviour.

Override with `--engine sander` (testing) or `--engine pmemd.cuda`
(force GPU even if pmemd is also present).

If the user has both `pmemd.cuda` and `pmemd` on PATH and is running
on a CPU-only node, **the auto-selection picks `pmemd.cuda` and the
job will fail at runtime** with a CUDA initialization error. Use
`--engine pmemd` explicitly in that case. (v1.3 does not probe the
host for actual GPU availability before selecting; that's a v2.4
nice-to-have.)
