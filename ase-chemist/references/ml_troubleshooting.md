# MACE troubleshooting + out-of-scope

Part of the v1.2 ML-potentials reference set. Companion files:
[`ml_method_selection.md`](ml_method_selection.md),
[`ml_validation_contract.md`](ml_validation_contract.md),
[`ml_failure_modes.md`](ml_failure_modes.md). Index:
[`ml_potentials.md`](ml_potentials.md).

## Troubleshooting

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

## Out of scope (explicitly, even in v1.2)

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
