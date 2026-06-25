# ase-chemist

> An Agent Skill that turns *"I want to simulate this molecule"* into a
> running calculation — with the method picked for the system at hand,
> not for whatever the user happened to type.

`ase-chemist` is a Claude Code skill for atomistic / molecular
simulation. Hand it a structure file and a question; it walks a
documented method-selection tree, picks the right calculator from
seven supported backends, runs the calculation through ASE, and
reports honestly when a request is past what v1 can deliver.

The skill's value isn't "here are seven backends, pick one." It's
*"given this structure, this task, and what's actually installed,
here's the right method and here's what it can and can't tell you."*

---

## What it can do

Seven backends, one consistent interface, one router:

| Backend | Reach for it when... | Through |
|---|---|---|
| **EMT** | Quick metallic answers — Al, Cu, Ag, Au, Ni, Pd, Pt + H/C/N/O adsorbates | `optimize.py` / `run_md.py` |
| **Lennard-Jones** | Toy systems, noble gases, methodology training | `optimize.py` / `run_md.py` |
| **TIP3P** | Pure-water MD where rigid O–H bonds matter | `run_md.py` |
| **GFN2-xTB** *(via tblite)* | Default for organic / main-group up to ~1k atoms | `optimize.py` / `run_md.py` / `single_point.py` |
| **MACE** *(MP-0 + OFF)* | Past the xTB size cliff (~1–2k atoms), with **mandatory cross-validation** against xTB | `optimize.py --calculator mace` / `run_md.py --calculator mace` |
| **Amber + GAFF2** | Production explicit-solvent MD on small organics (antechamber AM1-BCC → tleap → pmemd) | `parameterize_gaff2.py` → `run_amber.py` |
| **Gaussian DFT** | When publication-quality DFT actually matters — single-point, opt, frequency + thermochem | `gaussian_sp.py` / `gaussian_opt.py` / `gaussian_freq.py` |

Plus the boring-but-essential primitives:

- **Geometry optimization** — BFGS / FIRE / LBFGS — on any calculator.
- **Molecular dynamics** — NVE / NVT-Langevin / NVT-Nose–Hoover — on any calculator.
- **Single-point observables** — energy, forces, dipole, HOMO-LUMO, Mulliken charges, Wiberg bond orders.
- **Trajectory analysis** — RMSD, RMSF, energy drift, RDF; PNG plots + CSV alongside the input.
- **Structure building** — `ase.build` patterns for molecules, bulk crystals, surfaces with adsorbates.
- **Vibrations / Hessian / ZPE** — `ase.vibrations.Vibrations` (xTB-level) or `gaussian_freq.py` (DFT-level).

---

## What it looks like in use

**Organic single-point at xTB level**

> "Optimize `caffeine.xyz` and tell me the HOMO-LUMO gap. Don't actually run it."

Skill walks the method-selection tree: caffeine is organic + main-group → GFN2-xTB
(EMT would silently give nonsense). Writes:

```bash
python scripts/optimize.py --structure caffeine.xyz --calculator xtb \
    --xtb-method GFN2-xTB --output opt.traj
python scripts/single_point.py --structure opt.traj --calculator xtb \
    --xtb-method GFN2-xTB
```

…and flags that GFN2-xTB's raw eigenvalue gap is larger than the gap the
standalone `xtb` binary reports — different convention, documented in
`references/xtb.md`.

**Speeding up MD past the xTB size cliff**

> "Run NVT MD on a 5000-atom organic system at 300 K for 50 ps."

GFN2-xTB MD on 5000 atoms is impractical. Skill routes to **MACE-OFF**
(pure-organic foundation model) and turns on **mandatory cross-validation**
against GFN2-xTB every 1 ps. The MD aborts if force MAE exceeds 100 meV/Å —
the published rule of thumb for "trajectory drifted out of training
distribution":

```bash
python scripts/run_md.py --structure system.xyz --calculator mace \
    --ensemble nvt-langevin --temperature 300 --n-steps 50000 \
    --output md.traj
# validation.csv written every 1 ps; abort at MAE_F > 100 meV/Å
```

**DFT thermochemistry**

> "Compute G_298 for caffeine at B3LYP-D3/def2-TZVP."

DFT-level thermochem needs an explicit method/basis. Skill **refuses
silent defaults** — confirms charge / multiplicity / `%mem` / `%nprocshared`
with the user, then runs Opt → Freq:

```bash
python scripts/gaussian_opt.py --structure caffeine.xyz \
    --method "B3LYP EmpiricalDispersion=GD3BJ" --basis def2tzvp \
    --charge 0 --multiplicity 1 --convergence tight \
    --mem 8GB --nproc 8 --output opt.xyz

python scripts/gaussian_freq.py --structure opt.xyz \
    --method "B3LYP EmpiricalDispersion=GD3BJ" --basis def2tzvp \
    --charge 0 --multiplicity 1 --mem 8GB --nproc 8
```

Reports vibrational frequencies, ZPE, enthalpy, and Gibbs G at 298 K —
all parsed in-house, no third-party deps.

---

## Design principles

These are load-bearing. Touching them moves what the skill produces.

### 1. Right method for the system, not for the request

A "minimize this" prompt routes through a documented 3-step walk:
**task → calculator → install check**. What runs depends on system
size, chemistry, and what's actually installed — not on which
calculator's name appeared in the prompt. EMT on an organic gets
caught; GFN2-xTB on a 5000-atom system gets redirected to MACE.

### 2. Everything through ASE-or-our-own-code

Six of the seven backends speak ASE's `Calculator` pattern. Output parsing
that ASE doesn't cover (Gaussian frequencies, thermochem, MO
eigenvalues) lives in a small in-house regex helper —
`scripts/_gaussian_log.py`, ~100 lines of stdlib — not a third-party
output parser. The one exception is Amber MD: pmemd runs the
integration loop natively for performance reasons. That carve-out is
explicitly flagged in `references/amber.md` §1 and is under review.

### 3. Honest about limits

Every backend ships with a documented accuracy/cost ceiling, surfaced
in plain language when relevant:

- xTB MD past ~1k atoms is impractical → reach for MACE.
- MACE-medium tops out around 1–2k atoms on a 40 GB GPU → drop to
  small or shrink the system.
- ASE's `Amber` calculator is single-point only and rejects
  non-orthogonal cells → v1.3 shells out to pmemd directly.
- Gaussian's `read_gaussian_out` doesn't parse vibrational
  frequencies → the in-house log helper handles it.

The skill says "v1 can't deliver that" out loud rather than silently
producing plausible-but-wrong numbers.

### 4. Cross-validation is non-negotiable for ML potentials

Every MACE MD run validates against GFN2-xTB every 1 ps and aborts
when force MAE exceeds 100 meV/Å. Opt-out (`--no-validate`) is
**per-run, not the default**. This is the contract under which the
skill recommends MACE at all — without it, ML potentials produce
plausible-but-wrong PESs that users cannot spot.

See `references/ml_validation_contract.md` for the full protocol.

### 5. No DFT method/basis defaults

`gaussian_sp.py` / `gaussian_opt.py` / `gaussian_freq.py` **refuse to
run** without `--method`, `--basis`, `--charge`, `--multiplicity`,
`--mem`, `--nproc`. The wrong-physics failure (B3LYP/6-31G(d) silently
picked on a transition-metal system) is the failure mode v1 already
guards against elsewhere; same logic applies here. When asked
"what should I use?", the skill surfaces a recommendation
(ωB97X-D/def2-TZVP for organics; PBE0-D3(BJ)/def2-TZVP for transition
metals — `references/gaussian_method_selection.md`) and confirms before
running.

---

## Install

**Required (conda preferred on HPC):**

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib numpy
```

Pip-only fallback:

```bash
pip install ase tblite mdanalysis matplotlib numpy
```

**Optional backends — install only what you need:**

```bash
# MACE foundation models (v1.2+). CUDA strongly recommended.
pip install mace-torch

# Amber GAFF2 small-molecule MD (v1.3+). AmberTools25 is fully open-source.
conda install -c conda-forge ambertools

# Gaussian DFT (v1.4+). License-gated; install per https://gaussian.com/
# Source the env so g16 (or g09) is on PATH and GAUSS_EXEDIR / GAUSS_SCRDIR are set.
# No third-party parser needed — thermochem parsing is in-house.
```

Sanity-check after install:

```bash
python ase-chemist/scripts/check_env.py
```

The output ends with a one-line `[SUMMARY]` of what your environment
actually supports right now. The skill recommends a method that's
there — it doesn't ask the user to install something extra when EMT
or LJ would already cover the question.

---

## Layout

```
ase-chemist/
├── SKILL.md                  # trigger contract + method-selection tree
├── README.md                 # this file
├── scripts/                  # 14 files: 12 task scripts + 2 shared helpers (_calc.py, _gaussian_log.py); see SKILL.md for the catalog
├── references/               # 15 scoped reference files; read on demand by topic
└── evals/                    # 5 prompts for manual review (programmatic assertions: iteration 2)
```

References are intentionally small (1–4k chars each) so the model
loads only the section relevant to the task — `ml_validation_contract.md`,
`gaussian_log_parser.md` etc., navigable through the umbrella indices
`ml_potentials.md` / `gaussian.md`. The Amber carve-out is small
enough that `amber.md` is a single self-contained file (§1–§5) rather
than an index.

---

## Releases

- **v1.0 / v1.1** — Foundation. ASE built-ins (EMT, LJ, TIP3P), tblite
  (GFN1/GFN2-xTB), optimize / MD / single-point / trajectory analysis /
  structure building.
- **v1.2 — MACE.** MACE-MP-0 (89-element materials) + MACE-OFF
  (10-element organics) foundation models with mandatory cross-
  validation against GFN2-xTB.
- **v1.3 — Amber + GAFF2.** Small-molecule MD via antechamber AM1-BCC
  → parmchk2 → tleap → pmemd. Architecturally an outlier; carve-out
  documented and under review.
- **v1.4 — Gaussian DFT.** SP / Opt / Freq through
  `ase.calculators.gaussian.Gaussian`. No method/basis defaults. SMD
  as the documented water-solvent default. Thermochem parsing
  in-house — no cclib.

---

## What's coming

See [`PLAN.md`](../PLAN.md) for the v2 vision and milestones. The
short version: v2 is about **earning what v1.x built** — real
end-to-end integration tests, programmatic eval assertions,
Amber-carve-out resolution, SKILL.md slim — and **learning to compose
backends** (cheap → expensive ladders, multi-method validation,
workflow registry). v2.2+ adds CHGNet / Orb-v3 / biomolecular Amber
(ff19SB+OPC, OL21). v3+ takes on Gaussian extensions (TS / IRC /
post-HF / TDDFT) and free-energy / enhanced-sampling research
workflows.

---

## Notes for skill developers

- The **`SKILL.md` description field is the trigger contract.**
  Phrases enumerated there are what activates the skill in Claude
  Code. If trigger reliability regresses, optimize that field first.
- v1 was built against ASE current (`temperature_K=` is the canonical
  thermostat kwarg as of ASE 3.21.0) and `tblite` (the supported
  successor to the deprecated `xtb-python`). If you upgrade either,
  re-run the evals manually and update the references.
- Reference files are scoped (`ml_method_selection.md`,
  `gaussian_log_parser.md`, etc.) so the model navigates to the
  topic it needs without reading the whole chapter. Edit them as
  scoped files, not as one big chapter — the umbrella indices
  (`ml_potentials.md` / `gaussian.md`) just point. `amber.md` is
  self-contained (the v1.3 carve-out is small enough not to need
  splitting).
- The eval set has **no programmatic assertions** in v1. That's
  iteration 2's job — `PLAN.md` v2.0 milestones.
- See `CLAUDE.md` at the repo root for the load-bearing design
  decisions and the duplication rules across the three skill copies
  (`ase-chemist/`, `.claude/skills/ase-chemist/`,
  `~/.claude/skills/ase-chemist/`).
