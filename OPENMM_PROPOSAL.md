# `openmm-chemist` v1.0 — proposal

Working proposal for a **third sibling skill** alongside `ase-chemist`
and `amber-chemist`. Scope: small-molecule MD + optimization only,
through the OpenMM engine, focused on the surface that genuinely
nothing else in the workspace serves.

Three rounds of scoping cuts narrowed the surface from "generic
OpenMM MD" to "OpenMM-exclusive small-molecule MD/Opt." This doc is
the result.

## TL;DR

**Three capabilities, three scripts, one v1.0:**

1. **ML/MM small-mol-in-solvent** — MACE-OFF / ANI-2x / AIMNet2 treats
   the solute, TIP3P / OPC treats the solvent, coupled in one
   GPU-resident OpenMM `System`. The marquee.
2. **OpenFF SMIRNOFF in-process** — `openff-toolkit` parameterization
   → OpenMM `System` → MD/Opt. No `antechamber` round-trip, no
   `prmtop` export step.
3. **`CustomForce` restraints / biased MD-Opt** — string-expression
   forces (`CustomBondForce`, `CustomNonbondedForce`,
   `CustomExternalForce`) layered on a base FF.

**Why a new skill and not `ase-chemist` v1.5 / `amber-chemist` v1.1:**
the three slots together form a coherent OpenMM-native surface
(Python-first, GPU-resident, in-process). Folding any one of them
into a sibling skill is awkward — they share `_openmm.py`
infrastructure, share the `Simulation` / `Context` / `State` mental
model, and share the `state.xml` + `checkpoint.chk` restart format
(not `.rst7`). Better to land them together as their own scoped skill
than to scatter them across two skills that don't speak the same idiom.

## What this skill explicitly does NOT do

Out of scope for v1.0 — the skill **declines and routes** when asked:

- **Plain GAFF2 small-mol MD** → `amber-chemist` (or `ase-chemist` v1.3
  carve-out). Already canonical.
- **Biopolymer MD** (proteins, nucleic acids) → `amber-chemist` v1.1
  when it lands; not here.
- **T-REMD / Hamiltonian REMD / REST2** → `amber-chemist` for T-REMD;
  REST2 is a v1.1 candidate here but **not v1.0**.
- **MMPBSA / endpoint scoring** → `amber-chemist`.
- **Alchemical free energy** (`openmmtools.alchemy`, FEP, TI) →
  explicit v1.1 candidate.
- **PLUMED bridge** (metadynamics, umbrella sampling) → v1.1
  candidate via `openmm-plumed`.
- **AMOEBA / Drude polarizable** → v1.1 candidate. Not v1.0 because
  the small-mol audience overlap is small; the canonical use cases
  (ions, water clusters, polarizable solvents) are slightly outside
  the "small molecule" framing.
- **DFT** → `ase-chemist` v1.4 (Gaussian).

The skill's `SKILL.md` description field must enumerate triggers
tightly enough that the above don't accidentally route here. See
"Trigger boundary" below.

## The exclusive surface, in detail

### 1. ML/MM small-mol-in-solvent (the marquee)

**What it owns:** GPU-fast MD + Opt for a small-molecule solute
described by an ML potential, inside an explicit-solvent box
described by a classical FF, coupled in one `System`.

**Why nothing else here serves it:**

| Sibling path | Why it falls short |
|---|---|
| `ase-chemist` v1.2 MACE | Single-calculator. Putting MACE on a 5–20k atom solvated box exceeds the MACE-medium GPU ceiling (~1–2k atoms on 40 GB). ASE's multi-calculator partitioning works but drops to Python-loop integration speed, losing the GPU advantage that motivated MACE in the first place. |
| `amber-chemist` v1.0 | No ML path. |
| `ase-chemist` GFN2-xTB | Whole-system xTB on 10k atoms is the cliff that motivated MACE — going back to it isn't a path. |

**Script:** `omm_mlmm.py`

```
python scripts/omm_mlmm.py
    --task {md, optimize}
    --solute <pdb-or-xyz>             # the small molecule (~20-80 atoms)
    --ml-model {mace-off, ani-2x, aimnet2}
    --solvent {tip3p, opc, none}
    --box-padding 1.2                 # nm
    --ensemble {nvt-langevin, npt-monte-carlo}    # MD only
    --temperature 300 --pressure 1.0
    --n-steps 50000 --output md.traj
    --validate-against {xtb, smirnoff, gaff2, none}   # default 'xtb'
    --validation-interval 1000        # steps
```

`--solvent none` is rejected — vacuum small-mol ML-MD doesn't pay the
OpenMM setup cost over `ase-chemist`'s ASE-driver path. Script tells
the user to use `ase-chemist` instead.

### 2. OpenFF SMIRNOFF, in-process

**What it owns:** modern small-molecule FF (Sage 2.x, Parsley 1.x)
parameterized via `openff-toolkit` directly into an OpenMM `System`
— no `antechamber` AM1-BCC step, no `prmtop` export step.

**Honest framing on "exclusivity":** SMIRNOFF parameter sets aren't
OpenMM-exclusive (`Interchange.to_prmtop()` exports to Amber). The
*in-process* parameterize → MD/Opt loop is OpenMM-native, and that's
the value: a user with a SMILES string and a question goes from SMILES
to running MD in one script, no format conversions. Worth a slot.

**Script:** `omm_smirnoff.py`

```
python scripts/omm_smirnoff.py
    --task {md, optimize}
    --smiles "CC(=O)Oc1ccccc1C(=O)O"           # OR --structure
    --forcefield {openff-2.2.0, openff-1.3.0}
    --solvent {tip3p, opc, none}
    --ensemble {nvt-langevin, npt-monte-carlo}
    --temperature 300 --pressure 1.0
    --n-steps 50000 --output md.traj
```

### 3. CustomForce restraints / biased MD-Opt

**What it owns:** user-defined forces as string expressions
(`"k*(r-r0)^2"`, `"A*exp(-B*r) - C/r^6"`, arbitrary CV), compiled to
GPU kernels by OpenMM. Layered on a base FF (SMIRNOFF or, via
`parmed`, GAFF2).

**Honest framing on "exclusivity":** distance restraints in Amber's
`nmropt` cover the most common small-mol case. But `nmropt` is a
fixed-form `(r0, k, k2)` restraint system; `CustomForce` is arbitrary
expressions. The exclusive value is generality, not the common case.

**Script:** `omm_custom.py`

```
python scripts/omm_custom.py
    --task {md, optimize}
    --structure <pdb-or-xyz>
    --base-ff {smirnoff-2.2.0, gaff2-bridge, none}
    --force-type {bond, angle, nonbonded, external}
    --force-expr "k*(r-r0)^2"
    --force-params "k=100,r0=1.5"
    --force-atoms "1,7"               # indices the force acts on
    --solvent {tip3p, opc, none}
    --ensemble {nvt-langevin, npt-monte-carlo}
    --n-steps 50000 --output md.traj
```

## Cross-validation contract — extended for ML/MM

`ase-chemist` v1.2 ships a non-negotiable contract: every 1 ps of
MACE MD, re-evaluate the snapshot through GFN2-xTB, abort at
`MAE_F > 100 meV/Å`. v1.0 of `openmm-chemist` inherits the same
threshold and per-run opt-out semantics, with one extension and one
sharpening:

- **Compare on the ML region only.** Validating MM solvent forces is
  a category error — TIP3P/OPC aren't what the ML model claims to
  compute.
- **Default reference: GFN2-xTB on the ML region, out-of-process.**
  Same Validator pattern `ase-chemist` v1.2 already implements
  (`validate_ml_md.py`). Reused, not reinvented. The ML region is
  small (~20–80 atoms) so xTB is cheap even out-of-process.
- **Cheap-but-weaker alternative: `--validate-against smirnoff`** —
  SMIRNOFF runs as a shadow `Force` group (`setForceGroup(15)`,
  excluded from integration), forces queried per validation interval.
  Effectively free per-step, but the comparison is interpretively
  awkward: SMIRNOFF has its own approximation errors that ML is
  *meant to correct*, so disagreement is expected. Available, not
  default. Caveat documented in `references/ml_validation_in_openmm.md`.
- **Slots 2 and 3 don't need cross-validation** — analytic FFs only,
  no ML to police.

## Skill layout

```
openmm-chemist/
├── SKILL.md                       # trigger contract + method-selection tree
├── README.md                      # user-facing
├── scripts/
│   ├── _openmm.py                 # shared: system builder, integrator factory, state I/O, ML/MM partitioner
│   ├── check_env.py               # OpenMM, openmm-ml, openmm-torch, openff-toolkit, CUDA platforms
│   ├── omm_mlmm.py                # marquee: ML/MM small-mol-in-solvent
│   ├── omm_smirnoff.py            # OpenFF SMIRNOFF in-process
│   └── omm_custom.py              # CustomForce restraints / biases
├── references/
│   ├── README.md                  # index
│   ├── ml_mm_partition.md         # when ML/MM beats single-calc, partition recipe, size regime
│   ├── ml_validation_in_openmm.md # cross-validation contract — extended; xtb-vs-smirnoff trade
│   ├── smirnoff_in_process.md     # parameterize → MD/Opt loop; conversion to/from Amber prmtop
│   ├── custom_forces.md           # string-expression cookbook; common restraint geometries
│   ├── carveout_relationship.md   # sibling routing (this skill vs ase-chemist vs amber-chemist)
│   ├── failure_modes.md           # known issues + recovery
│   ├── extension_map.md           # AMOEBA, Drude, alchemy, REST2, PLUMED — where each would land
│   └── manual_lookup.md           # URLs to OpenMM, openmm-ml, openff-toolkit, openmm-torch docs
└── evals/evals.json
```

References intentionally small (1–4k chars each), same pattern as the
sibling skills.

## Trigger boundary

This is the load-bearing part. `SKILL.md`'s description field must
trigger on ML/MM-in-solvent, SMIRNOFF, and CustomForce *without*
swallowing prompts that belong to `ase-chemist` or `amber-chemist`.

| User says... | Routes to |
|---|---|
| *"MACE-OFF MD on caffeine in TIP3P water"* | **`openmm-chemist`** (marquee) |
| *"ANI-2x optimization of ibuprofen in water"* | **`openmm-chemist`** |
| *"SMIRNOFF parameterized aspirin in water, 100 ns NPT"* | **`openmm-chemist`** |
| *"OpenFF Sage 2.2 MD of acetate ion"* | **`openmm-chemist`** |
| *"distance restraint k=50 on C1–C7 during MD of butane in water"* | **`openmm-chemist`** (CustomBondForce) |
| *"GAFF2 NPT of benzene in water, restart from `.rst7`"* | **`amber-chemist`** (canonical) |
| *"vacuum MACE-OFF MD on a 50-atom organic"* | **`ase-chemist`** (driver overhead doesn't matter; no solvent partition) |
| *"GFN2-xTB optimization of glycine"* | **`ase-chemist`** |
| *"T-REMD on this drug-like molecule"* | **`amber-chemist`** |
| *"MMPBSA on this docked complex"* | **`amber-chemist`** |

The two trigger-boundary cases that warrant `borderline` tests:

- **Solvated MACE on a small molecule, where speed matters but the
  user typed *"MACE"* not *"OpenMM"*.** Either skill is defensible;
  `openmm-chemist` is the better answer when the system is solvated
  and trajectory is >10 ns. The model should defer to user preference
  and explain the size/speed trade.
- **SMIRNOFF parameterization where the user implies pmemd
  execution** (e.g., *"parameterize this with OpenFF and run NPT in
  Amber"*). Should route to `amber-chemist` with a `parmed`
  `Interchange.to_prmtop()` step, not to `openmm-chemist`.

## Test harness coverage

Extend `run_tests.sh` with namespace `o*` for OpenMM prompts. Target:
**6 new prompts**, growing the suite from 43 → 49:

| ID | Type | Tests |
|---|---|---|
| `o1_mlmm_md_solvated` | trigger | MACE-OFF MD on a small molecule in TIP3P → marquee routes correctly, emits cross-validation flags |
| `o2_mlmm_opt_solvated` | trigger | ANI-2x optimization in OPC water → `omm_mlmm.py --task optimize` |
| `o3_smirnoff_md` | trigger | OpenFF Sage 2.2 NPT MD → `omm_smirnoff.py` |
| `o4_custom_force` | trigger | CustomBondForce restraint during small-mol MD → `omm_custom.py` |
| `o5_mlmm_vacuum_defers` | borderline | MACE on a small molecule **in vacuum** → should route to `ase-chemist`, not stay here |
| `o6_mace_solvated_collision` | borderline | "MACE on caffeine in water" with no OpenMM hint → either skill defensible; checks router behavior |

## Install surface

```bash
# Required
conda install -c conda-forge openmm openff-toolkit openff-interchange parmed mdtraj

# ML/MM (marquee)
pip install openmm-ml          # MLPotential wrapper around openmm-torch
pip install openmm-torch       # TorchForce, GPU-resident TorchScript
pip install mace-torch         # MACE-OFF models
# ANI-2x and AIMNet2 come via openmm-ml or torchani / aimnet2 packages

# CUDA OpenMM build is required for production throughput
conda install -c conda-forge openmm cudatoolkit
```

`check_env.py` reports the OpenMM platform list (CUDA / OpenCL /
CPU / Reference), confirms `openmm-ml` import path, and lists which
ML models are downloadable / cached. `[SUMMARY]` line at the end,
matching the sibling skills.

## Versioning

- **v1.0** — three slots above, MD + Opt only, single-GPU only.
- **v1.1 candidates** (any one of these earns a release):
  - AMOEBA / Drude polarizable for ions and polarizable solvents.
  - Alchemical free energy via `openmmtools.alchemy` (single-step
    relative binding, hydration free energy).
  - REST2 (`openmmtools.multistate.ReplicaExchangeSampler` with
    Hamiltonian temperature scaling on the solute).
  - PLUMED bridge for metadynamics / umbrella sampling.
- **v1.2+** — multi-GPU MD, membrane systems (CHARMM-GUI → OpenMM),
  Drude on biomolecular sites (alongside `amber-chemist` v1.1).

## Sequencing rules (matches `CLAUDE.md` / `PLAN.md` style)

Wait until trigger tests pass against the dev source before syncing
to `.claude/skills/openmm-chemist/` and `~/.claude/skills/openmm-chemist/`.

1. **Phase 0** — Skill scaffolding. `SKILL.md` with description field
   (trigger contract), empty scripts directory, `references/README.md`
   index, empty `evals/evals.json`. One commit.
2. **Phase 1** — `_openmm.py` + `check_env.py`. `references/manual_lookup.md`
   and `carveout_relationship.md`. One commit. Adds no trigger tests
   yet (no scripts to invoke).
3. **Phase 2 — marquee.** `omm_mlmm.py` with `--task optimize` first
   (simpler than MD; no thermostat/barostat surface). Reference file
   `ml_mm_partition.md` and `ml_validation_in_openmm.md`. Add
   `o2_mlmm_opt_solvated` to `run_tests.sh`. One commit.
4. **Phase 3** — `omm_mlmm.py --task md`. Add `o1_mlmm_md_solvated`,
   `o5_mlmm_vacuum_defers`, `o6_mace_solvated_collision`. One commit.
5. **Phase 4** — `omm_smirnoff.py` + `smirnoff_in_process.md`. Add
   `o3_smirnoff_md`. One commit.
6. **Phase 5** — `omm_custom.py` + `custom_forces.md`. Add
   `o4_custom_force`. One commit.
7. **Phase 6 — sync.** `rsync` dev source to both loaded copies. Run
   full 49-prompt `run_tests.sh`. Fix regressions in dev, re-sync,
   re-test. Repeat until clean.
8. **Phase 7 — docs.** `README.md` (user-facing), `failure_modes.md`,
   `extension_map.md`. Update root `README.md` and `CLAUDE.md` to
   include the third skill in the duplication rules. One commit.

Seven commits, three new scripts, one new shared module, 8 new
reference files, 6 new trigger tests. Roughly matches the size of
`amber-chemist` v1.0 at landing, scaled down to v1.0's narrower
surface.

## Open questions

- **MACE-OFF element coverage on the solute.** MACE-OFF covers
  H, C, N, O, F, P, S, Cl, Br, I (10 elements). What does `omm_mlmm.py`
  do when the user's solute has Si or B? Reject at startup — silent
  substitution to MACE-MP-0 is exactly the wrong-physics failure mode
  v1 already guards against elsewhere.
- **Box-padding default.** `--box-padding 1.2` (nm) is reasonable for
  small molecules in TIP3P. Should be documented in
  `references/ml_mm_partition.md` §size-regime alongside throughput
  benchmarks once they exist.
- **GPU memory ceiling for ML/MM.** What's the practical solvent-box
  ceiling before the MM nonbonded list overwhelms a 40 GB GPU? Worth
  a one-sentence empirical note in `ml_mm_partition.md` once
  benchmarks exist.
- **SMIRNOFF version pinning.** Sage 2.2.0 vs Parsley 1.3.0 — which
  is the v1.0 default? Likely Sage 2.2.0 (newer, broader coverage),
  but document the choice in `smirnoff_in_process.md` §1.
- **What goes in `SKILL.md`'s description field.** The trigger
  contract is load-bearing; needs to enumerate ML/MM, SMIRNOFF, and
  CustomForce phrases tightly enough that `ase-chemist` MACE prompts
  and `amber-chemist` GAFF2 prompts don't bleed in. Draft this
  early; iterate against `o5` and `o6` borderline tests.

## Notes for future scope decisions

If demand for the v1.1 candidates is uneven, ship them piecewise
rather than as one big v1.1 release. Each is independent — alchemical
free energy needs `openmmtools.alchemy` and a new `omm_alchemy.py`;
REST2 needs `openmmtools.multistate` and a new `omm_rest2.py`;
PLUMED needs `openmm-plumed` and a new `omm_plumed.py` (or an
extension to `omm_mlmm.py` and `omm_smirnoff.py`'s flag surface).
None of them require touching the v1.0 scripts.

AMOEBA / Drude is the one v1.1 candidate that would meaningfully
broaden the skill beyond small molecules — it earns its keep on
ions, water clusters, and polarizable solvents. When that lands, the
skill's "small-molecule only" framing in v1.0 relaxes; consider
renaming `SKILL.md`'s description and updating
`references/carveout_relationship.md`.
