# MACE method-selection rules

Part of the v1.2 ML-potentials reference set. Companion files:
[`ml_validation_contract.md`](ml_validation_contract.md),
[`ml_failure_modes.md`](ml_failure_modes.md),
[`ml_troubleshooting.md`](ml_troubleshooting.md). Index:
[`ml_potentials.md`](ml_potentials.md).

The framing: ML potentials are an **accelerator on top of trusted
methods, not a replacement.** The cross-validation contract
(`ml_validation_contract.md`) is what makes that statement honest.

## When to reach for MACE

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

## How the bundled scripts wire this in

- `scripts/optimize.py --calculator mace [--mace-system-class ...]
  [--mace-size small|medium|large]`
- `scripts/run_md.py --calculator mace [...]`

See `ml_validation_contract.md` for the validation flags that
`run_md.py` adds when `--calculator mace` is used.
