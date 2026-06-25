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
    <a href="https://scaliaven.github.io/chemist/">website</a> &nbsp;·&nbsp;
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

> **Heads up — still in active development.** Expect rough edges and
> sizeable changes between releases; issue reports are welcome. A third
> `openmm-chemist` sibling is planned eventually — for now the focus is
> these two.

---

## What this is

`chemist` is the dev workspace for **two sibling Agent Skills** for [Claude Code](https://claude.com/claude-code) — small, scoped extensions that turn natural-language requests like *"thermalize this solvated ligand at 300 K"* into the right calculation, run through the right backend, with the limits stated up front.

- **[`ase-chemist`](ase-chemist/)** — atomistic / molecular simulation on top of [ASE](https://wiki.fysik.dtu.dk/ase/). Seven backends behind one method-selection router: ASE built-ins (EMT, LJ, TIP3P), [tblite-xTB](https://github.com/tblite/tblite), [MACE](https://github.com/ACEsuit/mace) foundation models, an Amber-GAFF2 carve-out for small-molecule MD, and Gaussian DFT (SP / Opt / Freq).
- **[`amber-chemist`](amber-chemist/)** — Amber-native MD sibling. Single-replica MD with restart / extend, **T-REMD as a first-class capability**, plus add-ons for cpptraj-driven analysis, single-point energies, and MMPBSA endpoint scoring.

Both ship a trigger-test harness that runs prompts through `claude -p` in fresh sessions to catch activation and method-selection drift.

> **This is not an application.** There's no library to import and no service to run. The skills are markdown contracts (`SKILL.md`) plus Python scripts; Claude Code loads them on demand based on what the user asked for.

---

## Why you might care

Comp-chem tooling tends to be either *"here are 50 tools, you figure it out"* (general-purpose ASE) or *"here's a black box, give me your structure"* (opinionated wrapper). These skills sit between, on a shared design rigor:

- **Right method for the system, not the request.** A *"minimize this molecule"* prompt walks a documented `task → calculator → install check` tree, each rule with a stated *why*. EMT on an organic gets caught; GFN2-xTB on a 5000-atom system gets redirected to MACE.
- **Honest about limits.** xTB MD stops being practical at ~1k atoms; MACE-medium tops out near 1–2k on a 40 GB GPU; ASE's `Amber` calculator can't drive production MD. These surface in plain language whenever they're load-bearing — never hidden.
- **Cross-validation is non-negotiable for ML potentials.** Every MACE MD run validates against GFN2-xTB every 1 ps and aborts at force MAE > 100 meV/Å. Opt-out is per-run, not the default — ML potentials produce plausible-but-wrong PESs users can't spot on their own.
- **No DFT method / basis defaults.** The Gaussian scripts refuse to run without explicit `--method` / `--basis` (plus charge, multiplicity, resources). A silently-picked B3LYP/6-31G(d) on a transition metal is the same wrong-physics failure mode guarded against elsewhere.

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
```

Other prompts route differently: *"compute G_298 for caffeine at B3LYP-D3/def2-TZVP"* → `gaussian_opt.py` → `gaussian_freq.py` (in-house thermochem parsing); *"build a Pt(111) slab with a CO adsorbate"* stays inline with `ase.build` — no script for a 5-line task.

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
pip install mace-torch                              # MACE — CUDA strongly recommended
conda install -c conda-forge ambertools             # Amber GAFF2 carve-out
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

`run_tests.sh` runs prompts in fresh `claude -p` sessions (180 s cap each), each tagged `trigger` (should activate + write correct code), `no_trigger` (should stay out), or `borderline` (either response defensible; human review).

```bash
python generate_test.py            # regenerate fixtures
bash run_tests.sh                  # full sweep
TIMEOUT_SECS=300 bash run_tests.sh # longer per-prompt cap
```

The cap is intentionally too short to finish a simulation — the test asks *"did Claude write the right code?"*, not *"did it run?"*. Every prompt says not to execute its output. `evals/evals.json` (per skill) holds richer prompts for manual review.

---

## Layout

```
chemist/
├── ase-chemist/      # skill #1 dev source — SKILL.md, README.md, scripts/, references/, evals/
├── amber-chemist/    # skill #2 dev source — same shape
├── .claude/skills/{ase,amber}-chemist/    # project copies (what `claude -p` loads)
├── ~/.claude/skills/{ase,amber}-chemist/  # user copies (kept in parity)
├── CLAUDE.md         # design decisions + three-copy sync rules
├── run_tests.sh / generate_test.py        # trigger-test harness + fixtures
└── test-inputs/ , results/                # generated fixtures + run logs (gitignored)
```

Each skill has **three** copies: dev source (edit here), the project copy, and the user copy. Tests load the copies, not the dev source — so `rsync` after every edit (see [Contributing](#contributing)).

---

## Project documentation

**`ase-chemist`:**

- [`ase-chemist/README.md`](ase-chemist/README.md) — the skill's
  user-facing README. Backends, examples, design principles, install.
  **Read this first if you want to understand what the skill does.**
- [`ase-chemist/SKILL.md`](ase-chemist/SKILL.md) — the trigger
  contract (description field), method-selection tree, scripts
  catalog. Editing the description field regresses or improves
  activation; treat it as load-bearing.
- [`ase-chemist/references/`](ase-chemist/references/) — 15 small
  scoped reference files (1–4k chars each). `ml_potentials.md` and
  `gaussian.md` are thin indices pointing at sub-files; `amber.md`
  is a single self-contained file (the v1.3 carve-out is small
  enough not to need splitting, and deep Amber lives in the sibling
  `amber-chemist` skill). Read only the file that matches your task.

**`amber-chemist`:**

- [`amber-chemist/README.md`](amber-chemist/README.md) — the skill's
  user-facing README. What v1.0 ships, what's deferred, layout, and
  the carve-out relationship with `ase-chemist`'s v1.3 Amber path.
- [`amber-chemist/SKILL.md`](amber-chemist/SKILL.md) — the trigger
  contract and method-selection tree (single-replica MD, T-REMD,
  add-ons, escape hatches).
- [`amber-chemist/references/`](amber-chemist/references/) — 14
  topic-scoped reference files (`md_core`, `remd`, `force_fields`,
  `analysis`, `scoring`, `failure_modes`, `extension_map`, …) plus an
  index `README.md`.

**Repo-level:**

- [`PLAN.md`](PLAN.md) — phase sequencing for v2 work on
  `ase-chemist`, the v2 vision proposal, and decisions deferred to
  usage data.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — decision memo on the
  paradigm: why this is shipped as skills rather than agents or an
  MCP server, with an optional de-duplication refactor sketch.
- [`CLAUDE.md`](CLAUDE.md) — load-bearing design decisions for
  Claude Code sessions working in this repo. The skill-copy
  duplication rules (now applied to **both** skills), the
  load-bearing carve-outs, the what-NOT-to-touch list.

## Plans

- **`openmm-chemist`** — eventual third sibling skill. No timeline yet;
  listed here so it isn't forgotten.
- **No plans for ORCA or Gromacs.** Both are free and arguably more
  popular than what ships here, but I don't have the bandwidth and
  wasn't familiar with either when I started. Rough guidance if you're
  picking a tool for your own work:
  - **MD / sampling** → OpenMM (or `amber-chemist` here, if you're
    already in the AMBER ecosystem).
  - **QM calculations** (geometry optimization, single points,
    frequencies) → Gaussian (`ase-chemist` v1.4 drives it).
  - **In between** — depends on system size vs. accuracy needed.
    Small + high accuracy → Gaussian. Large + lower accuracy → OpenMM.

---

## Contributing

Bug reports and feature requests welcome via GitHub issues. For changes that touch the trigger contract (`SKILL.md` `description` field) or method-selection rules, please open an issue first — those are the parts that move eval results.

Workflow for skill edits:

1. Edit dev source under `ase-chemist/` or `amber-chemist/`.
2. `rsync` to both loaded copies (`.claude/skills/...` and `~/.claude/skills/...`).
3. `bash run_tests.sh` and confirm no regressions on trigger / no-trigger prompts.
4. Update the relevant `references/*.md` if you changed a contract (cross-validation threshold, method-selection rule, deferral surface).

See [`CLAUDE.md`](CLAUDE.md) for the full design-decision rationale.

## License

Released under the [MIT License](LICENSE). The backends the skills orchestrate
(ASE, tblite/xTB, MACE, AmberTools, Gaussian) carry their own licenses and
citation requirements — install and cite each per its own terms.
