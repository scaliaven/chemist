# asechemist

Development workspace for the **`ase-simulation` Agent Skill** — a Claude Code
skill that orchestrates atomistic simulations (MD, geometry optimization,
vibrational analysis, NEB, structure building) on top of ASE, tblite-xTB,
EMT, TIP3P, **MACE foundation models** (v1.2+), and **Amber GAFF2**
small-molecule MD (v1.3+).

This repo is **not** an application. There is no library to import and no
service to run. Working here means editing the skill, regenerating test
fixtures, and re-running the trigger-test harness to check that changes
don't regress activation or method-selection behavior. v2 sequencing for
ML / Amber / Gaussian work is tracked in [`PLAN.md`](PLAN.md).

## Layout

```
asechemist/
├── ase-simulation/                  # skill dev source (edit here)
│   ├── SKILL.md, README.md
│   ├── scripts/
│   │   ├── check_env.py             # backends + CUDA + Amber detection, capability summary
│   │   ├── optimize.py              # BFGS/FIRE/LBFGS; calculators emt/lj/tip3p/xtb/mace
│   │   ├── run_md.py                # NVE / NVT-Langevin / NVT-Nose-Hoover; auto cross-validation w/ MACE
│   │   ├── single_point.py          # E + dipole/charges/HOMO-LUMO via tblite
│   │   ├── analyze_traj.py          # RMSD/RMSF/energy drift/RDF
│   │   ├── ml_calculator.py         # v1.2 — MACE factory, element-set routing, GPU detect
│   │   ├── validate_ml_md.py        # v1.2 — post-hoc cross-validation vs GFN2-xTB
│   │   ├── parameterize_gaff2.py    # v1.3 — antechamber AM1-BCC -> parmchk2 -> tleap
│   │   └── run_amber.py             # v1.3 — min/heat/density/prod via pmemd.cuda/pmemd/sander
│   ├── references/
│   │   ├── ase_core.md              # ASE I/O, build, optimizers, MD integrators, NEB
│   │   ├── xtb.md                   # tblite, GFN1/GFN2/GFN0/GFN-FF, observables, limits
│   │   ├── analysis.md              # trajectory analysis recipes
│   │   ├── ml_potentials.md         # v1.2 — MACE method-selection, cross-validation contract
│   │   ├── amber.md                 # v1.3 — GAFF2 small-mol pipeline; protein/NA -> v2.3
│   │   └── gaussian.md              # STUB — v2.4 scope + detection spec
│   └── evals/evals.json
├── .claude/skills/ase-simulation/   # project-scoped copy loaded by `claude -p`
├── ~/.claude/skills/ase-simulation/ # user-scoped copy (kept in parity with project)
├── PLAN.md                          # v2 phase sequencing (Phase 0 -> 1 -> 2 -> deferred)
├── generate_test.py                 # fixture generator
├── run_tests.sh                     # trigger-test harness (14 prompts, v1.0 -> v1.3)
├── test-inputs/                     # generated fixtures (gitignored)
└── results/                         # per-run logs + .status (gitignored)
```

> The dev source under `ase-simulation/` and the loaded copies under
> `.claude/skills/ase-simulation/` and `~/.claude/skills/ase-simulation/`
> can drift. Tests run against the loaded copies. Sync after edits:
>
> ```bash
> rsync -a --delete ase-simulation/ .claude/skills/ase-simulation/
> rsync -a --delete ase-simulation/ ~/.claude/skills/ase-simulation/
> diff -rq ase-simulation .claude/skills/ase-simulation     # confirm parity
> diff -rq ase-simulation ~/.claude/skills/ase-simulation   # both copies
> ```
>
> [`PLAN.md`](PLAN.md) §"Sequencing rules" says wait until trigger tests pass
> against dev before syncing — `run_tests.sh` invokes `claude -p` which loads
> the loaded copy, so practically the order is "edit dev → sync → test → fix
> in dev → sync → test" until clean.

## Quickstart

```bash
# 0. (Optional, v1.2+) MACE foundation models. CUDA recommended.
pip install mace-torch

# 0. (Optional, v1.3+) Amber GAFF2 small-molecule MD pipeline.
conda install -c conda-forge ambertools

# 1. Sanity-check the simulation environment
python ase-simulation/scripts/check_env.py

# 2. Regenerate fixtures (caffeine.xyz, cluster.xyz, ar108.xyz, md.traj)
python generate_test.py

# 3. Run the trigger-test suite (writes results/<id>.{log,status})
bash run_tests.sh

# longer per-prompt budget (default 180s; ~42 min total at 14 prompts)
TIMEOUT_SECS=300 bash run_tests.sh

# 4. Skim outcomes
for f in results/*.status; do
  printf "%-22s %s\n" "$(basename "$f" .status)" "$(cat "$f")"
done
```

The harness exits non-zero if any prompt timed out or errored. Status values
are `ok`, `timeout`, or `error:<rc>` (124/137 are GNU `timeout` codes).

## What the test harness does

`run_tests.sh` runs **fourteen** prompts in fresh `claude -p` sessions with a
180 s wall-clock cap each, tagged as one of:

- **`trigger`** — the skill should activate and produce a correct ASE script.
- **`no_trigger`** — generic prompts that should not invoke the skill.
- **`borderline`** — definitional questions or graceful-deferral cases where
  either response is defensible; for human review.

Coverage by version:

| Version | Prompts | Tests |
|---|---|---|
| v1.0/v1.1 baseline | `p1`–`p5` (trigger), `p6`–`p7` (no_trigger), `p8`–`p9` (borderline) | xTB / EMT / LJ / TIP3P, build, analyze |
| v1.2 — MACE | `p10_mace_named`, `p11_size_cliff` (trigger) | foundation-model trigger phrases, size-cliff method selection |
| v1.3 — Amber GAFF2 | `p12_gaff2_named`, `p13_antechamber` (trigger), `p14_protein_md` (borderline) | GAFF2 / antechamber triggers, honest v2.3 deferral on proteins |

The 180 s budget is intentionally too short to actually run a simulation.
The test asks "did Claude write the right code?", not "did the code finish?"
— every prompt instructs the model not to execute its output. Preserve that
when editing prompts.

`evals/evals.json` is a separate set of five richer prompts with free-form
expected outputs for **manual** review. v1 has no programmatic assertions;
adding stable ones is iteration 2's job.

## Skill design

- [`ase-simulation/README.md`](ase-simulation/README.md) — install, backends,
  what's in each version, what's coming in v2.2+.
- [`ase-simulation/SKILL.md`](ase-simulation/SKILL.md) — the trigger contract
  (description field), method-selection tree, scripts catalog. Editing the
  description regresses or improves activation; treat it as load-bearing.
- [`ase-simulation/references/ml_potentials.md`](ase-simulation/references/ml_potentials.md)
  — MACE method-selection, the cross-validation contract (1 ps cadence,
  MAE_F > 100 meV/Å abort), known failure modes.
- [`ase-simulation/references/amber.md`](ase-simulation/references/amber.md)
  — GAFF2 small-molecule pipeline, force-field choices, engine selection,
  troubleshooting.
- [`PLAN.md`](PLAN.md) — phase sequencing for v2 work and decisions
  deferred to usage data.
- [`CLAUDE.md`](CLAUDE.md) — load-bearing design decisions (method
  selection, why `tblite` is preferred over `xtb-python`, what's
  intentionally out of v1) and what to preserve when editing.
