# MACE known failure modes + GPU/CPU notes

Part of the v1.2 ML-potentials reference set. Companion files:
[`ml_method_selection.md`](ml_method_selection.md),
[`ml_validation_contract.md`](ml_validation_contract.md),
[`ml_troubleshooting.md`](ml_troubleshooting.md). Index:
[`ml_potentials.md`](ml_potentials.md).

## Known failure modes

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

## GPU/CPU notes

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
