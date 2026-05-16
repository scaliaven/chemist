<h1 align="center">chemist</h1>

<p align="center">
  <strong>Two Claude Code skills that take computational chemistry seriously.</strong><br>
  Documented method selection over feature lists.
  Honest limits over silent fallbacks.
  Mandatory cross-validation over <em>"just trust the ML potential."</em>
</p>

<p align="center">
  <sub>
    <a href="ase-chemist/">ase-chemist</a> &nbsp;·&nbsp;
    <a href="amber-chemist/">amber-chemist</a> &nbsp;·&nbsp;
    <a href="PLAN.md">roadmap</a> &nbsp;·&nbsp;
    <a href="run_tests.sh">test harness</a>
  </sub>
</p>

<p align="center">
  <sub>
    Stack:
    <code>ASE</code> ·
    <code>tblite-xTB</code> ·
    <code>MACE-MP-0 / MACE-OFF</code> ·
    <code>AmberTools (GAFF2, pmemd, cpptraj, MMPBSA)</code> ·
    <code>Gaussian DFT</code>
  </sub>
</p>

---

## What this is

`chemist` is the dev workspace for **two sibling Agent Skills** for [Claude Code](https://claude.com/claude-code) — small, scoped extensions that turn natural-language requests like *"thermalize this protein-ligand complex at 300 K"* into the right calculation, run through the right backend, with the limits stated up front.

- **[`ase-chemist`](ase-chemist/)** — atomistic / molecular simulation on top of [ASE](https://wiki.fysik.dtu.dk/ase/). Seven backends behind one method-selection router: ASE built-ins (EMT, LJ, TIP3P), [tblite-xTB](https://github.com/tblite/tblite), [MACE](https://github.com/ACEsuit/mace) foundation models, an Amber-GAFF2 carve-out for small-molecule MD, and Gaussian DFT (SP / Opt / Freq).
- **[`amber-chemist`](amber-chemist/)** — Amber-native MD sibling. Single-replica MD with restart / extend, **T-REMD as a first-class v1.0 capability**, plus add-ons for cpptraj-driven analysis, single-point energies, and MMPBSA endpoint scoring.

Both ship a trigger-test harness that runs **31 prompts** through `claude -p` in fresh sessions to catch activation and method-selection drift between releases.

> **This is not an application.** There's no library to import and no service to run. The skills are markdown contracts (`SKILL.md`) plus Python scripts; Claude Code loads them on demand based on what the user asked for.

---

## Why you might care

Computational-chemistry tooling tends toward two failure modes:

- *"here are 50 tools, you figure it out"* — every general-purpose ASE script
- *"here's a black box, give me your structure"* — every opinionated wrapper

Both skills land between them, on a shared design rigor:

<table>
<tr>
<td width="50%" valign="top">

### Right method for the system, not the request

A *"minimize this molecule"* prompt walks a documented 3-step tree: **task → calculator → install check**. EMT on an organic gets caught. GFN2-xTB MD on a 5000-atom system gets redirected to MACE. Each rule has a stated *why*.

</td>
<td width="50%" valign="top">

### Honest about limits

xTB MD stops being practical at ~1k atoms. MACE-medium tops out near 1–2k atoms on a 40 GB GPU. ASE's `Amber` calculator can't drive production MD. Gaussian's `read_gaussian_out` doesn't parse vibrational frequencies. **None of those are hidden** — they surface in plain language whenever they're load-bearing.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Cross-validation is non-negotiable for ML potentials

Every MACE MD run validates against GFN2-xTB every 1 ps and aborts when force MAE exceeds 100 meV/Å. Opt-out (`--no-validate`) is **per-run, not the default**. ML potentials produce plausible-but-wrong PESs that users can't spot on their own — the contract under which the skill recommends MACE at all is that it doesn't.

</td>
<td width="50%" valign="top">

### No DFT method / basis defaults

The Gaussian scripts refuse to run without an explicit `--method` and `--basis` (plus `--charge`, `--multiplicity`, `--mem`, `--nproc`). Wrong-physics defaults — B3LYP/6-31G(d) silently picked on a transition-metal system — are the same failure mode v1 already guards against elsewhere. Same logic, same answer.

</td>
</tr>
</table>

If those principles match how you'd want a simulation tool to behave, the codebase is worth a read. If you'd rather something that *"just works"* without guardrails, you'll find them in the way.

---

## A minute in the skill

**A user types this in a Claude Code session in their working directory:**

> *"Run NVT MD on a 5000-atom organic system at 300 K for 50 ps. Don't actually run it — I just want the command."*

**`ase-chemist` activates and does this:**

1. Walks the method-selection tree. GFN2-xTB MD on 5000 atoms is impractical (xTB size cliff at ~1k atoms). Routes to **MACE-OFF** (pure-organic foundation model, element-set auto-detected).
2. Turns on **mandatory cross-validation** against GFN2-xTB every 1 ps. The MD aborts if force MAE exceeds 100 meV/Å — the published rule of thumb for *"trajectory drifted out of training distribution."*
3. Writes a runnable command and the *why*:

```bash
python scripts/run_md.py --structure system.xyz --calculator mace \
    --ensemble nvt-langevin --temperature 300 --n-steps 50000 \
    --output md.traj
# validation.csv written every 1 ps; aborts at MAE_F > 100 meV/Å
# (cross-validation contract — see references/ml_validation_contract.md)
```

A different prompt — *"compute G_298 for caffeine at B3LYP-D3/def2-TZVP"* — routes to `gaussian_opt.py` → `gaussian_freq.py`, confirms `%mem` / `%nprocshared` first, and parses the thermochemistry block in-house (no third-party parser). A *"build a Pt(111) slab with a CO adsorbate and relax it"* prompt stays inline with `ase.build` — no script for a 5-line task. The router does the right thing in each case, and says what it's doing.

See [`ase-chemist/README.md`](ase-chemist/README.md) and [`amber-chemist/README.md`](amber-chemist/README.md) for the full user-facing walkthroughs.

---

## Backends at a glance

| Backend | Reach for it when... | Skill | Through |
|---|---|---|---|
| **EMT** | Quick metallic answers — Al, Cu, Ag, Au, Ni, Pd, Pt + H/C/N/O | `ase-chemist` | `optimize.py` / `run_md.py` |
| **Lennard-Jones** | Toy systems, noble gases, methodology training | `ase-chemist` | `optimize.py` / `run_md.py` |
| **TIP3P** | Pure-water MD where rigid O–H bonds matter | `ase-chemist` | `run_md.py` |
| **GFN2-xTB** *(tblite)* | Default for organic / main-group up to ~1k atoms | `ase-chemist` | `optimize.py` / `run_md.py` / `single_point.py` |
| **MACE** *(MP-0 + OFF)* | Past the xTB size cliff (~1–2k atoms), with mandatory cross-validation | `ase-chemist` | `optimize.py --calculator mace` / `run_md.py --calculator mace` |
| **Amber + GAFF2** | Small-mol production MD, plain NPT (carve-out — deeper Amber lives next door) | `ase-chemist` | `parameterize_gaff2.py` → `run_amber.py` |
| **Gaussian DFT** | Publication-quality DFT — SP, Opt, Freq + thermochem | `ase-chemist` | `gaussian_sp.py` / `gaussian_opt.py` / `gaussian_freq.py` |
| **Amber (deep)** | Restart / extend, T-REMD, implicit GB, MMPBSA, cpptraj analysis | `amber-chemist` | `amber_run.py` (easy mode) or `amber_md.py` / `amber_remd.py` directly |

---

## Install

The two skills install independently — only what you need. Conda is preferred on HPC; pip works for laptops.

<details>
<summary><b><code>ase-chemist</code></b> — required + optional backends</summary>

```bash
# Required
conda install -c conda-forge ase tblite-python mdanalysis matplotlib numpy
# Pip-only fallback (libgfortran-fragile on some HPC):
pip install ase tblite mdanalysis matplotlib numpy

# Optional, install only what you need
pip install mace-torch                              # MACE (v1.2+) — CUDA strongly recommended
conda install -c conda-forge ambertools             # Amber GAFF2 carve-out (v1.3+)
# Gaussian: license-gated; install per https://gaussian.com/

# Sanity-check what your environment actually supports
python ase-chemist/scripts/check_env.py
```

</details>

<details>
<summary><b><code>amber-chemist</code></b> — AmberTools + MPI / CUDA</summary>

```bash
# Required — AmberTools25 is fully open-source
conda install -c conda-forge ambertools

# T-REMD needs MPI builds (pmemd.MPI / pmemd.cuda.MPI)
# MMPBSA.py.MPI is shipped with AmberTools

python amber-chemist/scripts/check_env.py
```

</details>

`check_env.py` ends with a one-line `[SUMMARY]` listing exactly which workflows the box can run right now. The skills recommend methods that are actually installed — they won't ask the user to install Gaussian when EMT or LJ would already cover the question.

---

## The trigger-test harness

`run_tests.sh` runs **31 prompts** in fresh `claude -p` sessions with a 180 s wall-clock cap each. Each prompt is tagged:

- **`trigger`** — the skill should activate and produce a correct script.
- **`no_trigger`** — generic prompts that should not invoke the skill.
- **`borderline`** — definitional questions or graceful-deferral cases where either response is defensible; for human review.

```bash
python generate_test.py            # regenerate fixtures
bash run_tests.sh                  # full sweep, ~90 min at default timeout
TIMEOUT_SECS=300 bash run_tests.sh # longer per-prompt cap

for f in results/*.status; do
  printf "%-22s %s\n" "$(basename "$f" .status)" "$(cat "$f")"
done
```

<details>
<summary><b>What the 31 prompts actually cover</b></summary>

**`ase-chemist` — 17 prompts**

| Version | Prompts | Tests |
|---|---|---|
| v1.0 / v1.1 baseline | `p1`–`p5` (trigger), `p6`–`p7` (no_trigger), `p8`–`p9` (borderline) | xTB / EMT / LJ / TIP3P / build / analyze |
| v1.2 — MACE | `p10_mace_named`, `p11_size_cliff` | foundation-model triggers, size-cliff method selection |
| v1.3 — Amber GAFF2 | `p12_gaff2_named`, `p13_antechamber`, `p14_protein_md` | GAFF2 / antechamber triggers, v2.3 protein deferral |
| v1.4 — Gaussian DFT | `p15_gaussian_sp`, `p16_gaussian_freq`, `p17_dft_no_method` | DFT triggers, no-defaults policy enforcement |

**`amber-chemist` — 14 prompts (all v1.0)**

| Area | Prompts | Tests |
|---|---|---|
| MD core | `a1_md_named`, `a2_extend`, `a4_implicit`, `a12_collision` | named GAFF2 NPT, restart/extend, implicit GB, trigger collision with `ase-chemist` |
| T-REMD | `a3_remd`, `a5_demux`, `a11_remd_ladder`, `a14_remd_no_mpi` | ladder, demux, ladder tuning, no-MPI graceful deferral |
| Add-ons | `a6_mmpbsa`, `a7_alanine`, `a8_cpptraj`, `a9_esander` | MMPBSA / alanine scan / cpptraj analysis / per-frame esander |
| Deferred features | `a10_ff19sb`, `a13_amd_borderline` | ff19SB biopolymer deferral, aMD deferral |

</details>

The 180 s budget is intentionally too short to actually run a simulation — the test asks *"did Claude write the right code?"*, not *"did the code finish?"*. Every prompt instructs the model not to execute its output. `evals/evals.json` (per skill) is a separate set of 5 richer prompts with free-form expected outputs for manual review.

---

## Layout

```
chemist/
├── ase-chemist/                       # skill #1 dev source — edit here
│   ├── SKILL.md                          # trigger contract + method-selection tree
│   ├── README.md                         # user-facing README
│   ├── scripts/                          # 12 scripts (optimize, run_md, gaussian_*, …)
│   ├── references/                       # 15 scoped reference files
│   └── evals/evals.json                  # 5 prompts for manual review
├── amber-chemist/                     # skill #2 dev source — edit here
│   ├── SKILL.md
│   ├── README.md
│   ├── scripts/                          # 9 scripts (amber_run, amber_md, amber_remd, …)
│   ├── references/                       # 15 topic-scoped reference files
│   └── evals/evals.json
├── .claude/skills/{ase,amber}-chemist/    # project skill copies (what claude -p loads)
├── ~/.claude/skills/{ase,amber}-chemist/  # user skill copies (kept in parity)
├── PLAN.md                            # v2 vision + phase sequencing (ase-chemist)
├── CLAUDE.md                          # design decisions for Claude Code sessions
├── generate_test.py                   # fixture generator
├── run_tests.sh                       # trigger-test harness (31 prompts: 17 + 14)
├── test-inputs/                       # generated fixtures (gitignored)
└── results/                           # per-run logs + .status (gitignored)
```

Each skill has **three** copies on the machine: dev source, the project skill copy under `.claude/skills/`, and the user skill copy under `~/.claude/skills/`. Tests run against the loaded copies, not the dev source. After every edit:

```bash
# ase-chemist
rsync -a --delete ase-chemist/ .claude/skills/ase-chemist/
rsync -a --delete ase-chemist/ ~/.claude/skills/ase-chemist/

# amber-chemist
rsync -a --delete amber-chemist/ .claude/skills/amber-chemist/
rsync -a --delete amber-chemist/ ~/.claude/skills/amber-chemist/

# parity check
diff -rq ase-chemist .claude/skills/ase-chemist
diff -rq amber-chemist .claude/skills/amber-chemist
```

---

## Releases

**`ase-chemist`**

| Version | What landed |
|---|---|
| **v1.0 / v1.1** | ASE built-ins (EMT, LJ, TIP3P), tblite (GFN1/GFN2-xTB), optimize / MD / single-point / trajectory analysis / structure building. |
| **v1.2** | MACE-MP-0 (89-element materials) and MACE-OFF (10-element organics) with mandatory cross-validation against GFN2-xTB. |
| **v1.3** | Amber + GAFF2 small-molecule MD via antechamber AM1-BCC → parmchk2 → tleap → pmemd. Architecturally an outlier; carve-out documented and under review. |
| **v1.4** | Gaussian DFT — SP / Opt / Freq through `ase.calculators.gaussian.Gaussian`. No method/basis defaults. SMD as the water-solvent default. Thermochem parsing in-house — no `cclib`. |

**`amber-chemist`**

| Version | What landed |
|---|---|
| **v1.0** | Single-replica MD (stages, restart, extend, restraints, barostats, implicit GB), T-REMD with auto temperature ladder and exchange-rate report, easy mode, add-ons for SP / cpptraj analysis / MMPBSA. |
| **v1.1** *(planned)* | ff19SB+OPC proteins, OL21 nucleic acids, full tleap-from-PDB system prep with pdb4amber and disulfide handling. |

---

## What's coming

See [`PLAN.md`](PLAN.md) for the v2 vision and milestones. The short version:

- **v2 (`ase-chemist`)** — earning what v1.x built: end-to-end integration tests, programmatic eval assertions, Amber-carve-out resolution, `SKILL.md` slimming. Then learning to compose backends: cheap → expensive ladders, multi-method validation, workflow registry.
- **v2.2+** — CHGNet (charge-aware materials), Orb-v3 (built-in confidence head), committee-uncertainty heads on a frozen MACE backbone.
- **v2.3** — biopolymer Amber: ff19SB+OPC, OL21, full system prep.
- **v3+** — Gaussian extensions (TS / IRC / NBO / post-HF / TDDFT), free-energy methods (TI / FEP / MBAR), enhanced sampling (REMD, metadynamics, umbrella sampling), QM/MM, constant-pH MD.

**Out of scope for the foreseeable:** VASP, Quantum ESPRESSO, SLURM/HPC submission templates, web GUIs. These are listed in `ase-chemist/README.md` and `PLAN.md` Phase 3.

---

## Project documentation

<table>
<tr>
<td width="50%" valign="top">

**`ase-chemist`**

- [`README.md`](ase-chemist/README.md) — user-facing: backends, examples, design principles, install. Start here to understand what the skill does.
- [`SKILL.md`](ase-chemist/SKILL.md) — the trigger contract (`description` field), method-selection tree, scripts catalog. Load-bearing for activation.
- [`references/`](ase-chemist/references/) — 15 small scoped reference files (1–4k chars each). `ml_potentials.md` and `gaussian.md` are thin indices; `amber.md` is self-contained.

</td>
<td width="50%" valign="top">

**`amber-chemist`**

- [`README.md`](amber-chemist/README.md) — user-facing: what v1.0 ships, what's deferred, carve-out relationship.
- [`SKILL.md`](amber-chemist/SKILL.md) — trigger contract + method-selection tree (single-replica MD, T-REMD, add-ons, escape hatches).
- [`references/`](amber-chemist/references/) — 15 topic-scoped files (`md_core`, `remd`, `force_fields`, `analysis`, `scoring`, `failure_modes`, `extension_map`, …).

</td>
</tr>
</table>

**Repo-level:** [`PLAN.md`](PLAN.md) for phase sequencing · [`CLAUDE.md`](CLAUDE.md) for load-bearing design decisions and the three-copy sync rules.

---

## Contributing

Bug reports and feature requests welcome via GitHub issues. For changes that touch the trigger contract (`SKILL.md` `description` field) or method-selection rules, please open an issue first — those are the parts that move eval results.

Workflow for skill edits:

1. Edit dev source under `ase-chemist/` or `amber-chemist/`.
2. `rsync` to both loaded copies (`.claude/skills/...` and `~/.claude/skills/...`).
3. `bash run_tests.sh` and confirm no regressions on trigger / no-trigger prompts.
4. Update the relevant `references/*.md` if you changed a contract (cross-validation threshold, method-selection rule, deferral surface).

See [`CLAUDE.md`](CLAUDE.md) for the full design-decision rationale.
