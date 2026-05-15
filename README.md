# chemist

> A development workspace for two Agent Skills that take computational
> chemistry seriously: documented method selection over feature-list
> mentality, honest limits over silent fallbacks, mandatory cross-
> validation over *"just trust the ML potential."*

`chemist` is the dev workspace for **two sibling Claude Code skills**:
**Disclaimer**: this whole thing is still in development mode, so expect rough edges and vast changes. If you find any issues, please report them. I plan to write a third openmm-chemist skill eventually, but for now I'm focused on these two:

- [**`ase-chemist`**](ase-chemist/) — atomistic / molecular simulation
  on top of ASE. Bundles seven backends (ASE built-ins, tblite-xTB,
  MACE foundation models, Amber-GAFF2 carve-out, Gaussian DFT) behind
  one method-selection router.
- [**`amber-chemist`**](amber-chemist/) — Amber-native, MD-first
  sibling. Single-replica MD with restart/extend, T-REMD as a v1.0
  first-class capability, plus add-ons for cpptraj-driven analysis,
  single-point energies, and MMPBSA endpoint scoring.

Both ship a trigger-test harness that runs prompts through `claude -p`
in fresh sessions to catch activation and method-selection drift
between releases — **31 prompts total** (17 for `ase-chemist`,
14 for `amber-chemist`).

This is **not** an application — there's no library to import and no
service to run. Working here means editing the skills, regenerating
test fixtures, syncing the loaded copies, and shipping commits on
`dev`. v2 sequencing for `ase-chemist` is tracked in
[`PLAN.md`](PLAN.md).

---

## Why this project might be worth a read

Computational-chemistry tooling tends toward two failure modes:
*"here are 50 tools, you figure it out"* (every general-purpose ASE
script) and *"here's a black box, give me your structure"* (every
opinionated wrapper). Both skills land between them on a shared
design rigor — illustrated below with `ase-chemist`'s concrete rules;
`amber-chemist` applies the same principles inside the Amber pipeline
(honest deferral on biopolymers / free energy / aMD, no silent
defaults for force-field choice or REMD ladders, restart/extend that
fails loudly rather than silently chunk-mismatching):

1. **Right method for the system, not for the request.** A *"minimize
   this molecule"* prompt walks a documented 3-step tree (task →
   calculator → install check) before doing anything. EMT on an
   organic gets caught; GFN2-xTB MD on a 5000-atom system gets
   redirected to MACE; Gaussian DFT refuses to run without explicit
   method/basis. Each rule has a stated *why*.

2. **Everything through ASE-or-our-own-code.** Seven backends, one
   Calculator pattern. Output parsing that ASE doesn't cover lives in
   a small in-house regex helper (`scripts/_gaussian_log.py`,
   stdlib-only) — not a third-party parser. The one exception (Amber
   MD running natively in pmemd) is explicitly flagged in
   `ase-chemist/references/amber.md` §1 and under review.

3. **Honest about limits.** xTB MD stops at ~1k atoms. MACE-medium
   tops out around 1–2k atoms on a 40 GB GPU. ASE's `Amber` calculator
   can't drive production MD. Gaussian's `read_gaussian_out` doesn't
   parse vibrational frequencies. **None of these are hidden** —
   they're surfaced in plain language whenever relevant.

4. **Cross-validation is non-negotiable for ML potentials.** Every
   MACE MD run validates against GFN2-xTB every 1 ps and aborts when
   force MAE exceeds 100 meV/Å. Opt-out is per-run, not the default.

5. **No DFT method/basis defaults.** Gaussian scripts refuse to
   silently pick — wrong-physics defaults (B3LYP/6-31G(d) on a
   transition-metal system) are the same failure mode v1 already
   guards against elsewhere.

If those principles match how you'd want a simulation tool to
behave, the codebase is worth a read. If you'd rather something
that *"just works"* without guardrails, you'll find them in the way.

For the user-facing version of this story (with concrete examples
and the install path), see
[`ase-chemist/README.md`](ase-chemist/README.md) and
[`amber-chemist/README.md`](amber-chemist/README.md).

---

## Layout

```
chemist/
├── ase-chemist/                    # skill #1 dev source — edit here
│   ├── SKILL.md                       # trigger contract + method-selection tree
│   ├── README.md                      # user-facing README
│   ├── scripts/                       # 12 scripts (optimize, run_md, gaussian_*, …)
│   ├── references/                    # 15 small scoped reference files
│   └── evals/evals.json               # 5 prompts for manual review
├── amber-chemist/                     # skill #2 dev source — edit here
│   ├── SKILL.md                       # trigger contract + method-selection tree
│   ├── README.md                      # user-facing README
│   ├── scripts/                       # 9 scripts (amber_run, amber_md, amber_remd, …)
│   ├── references/                    # 15 topic-scoped reference files
│   └── evals/evals.json               # 5 prompts for manual review
├── .claude/skills/{ase,amber}-chemist/   # project skill copies (loaded by `claude -p`)
├── ~/.claude/skills/{ase,amber}-chemist/ # user skill copies (kept in parity)
├── PLAN.md                            # v2 vision + phase sequencing (ase-chemist)
├── CLAUDE.md                          # design decisions for Claude Code sessions
├── generate_test.py                   # fixture generator
├── run_tests.sh                       # trigger-test harness (31 prompts: 17 ASE + 14 Amber)
├── test-inputs/                       # generated fixtures (gitignored)
└── results/                           # per-run logs + .status (gitignored)
```

Each skill has **three** copies on this machine: the dev source under
`{ase,amber}-chemist/`, the project skill copy under `.claude/skills/`,
and the user skill copy under `~/.claude/skills/`. Tests run against
the loaded copies, not the dev source. Sync after every edit:

```bash
# ase-chemist
rsync -a --delete ase-chemist/ .claude/skills/ase-chemist/
rsync -a --delete ase-chemist/ ~/.claude/skills/ase-chemist/
diff -rq ase-chemist .claude/skills/ase-chemist     # confirm parity
diff -rq ase-chemist ~/.claude/skills/ase-chemist

# amber-chemist
rsync -a --delete amber-chemist/ .claude/skills/amber-chemist/
rsync -a --delete amber-chemist/ ~/.claude/skills/amber-chemist/
diff -rq amber-chemist .claude/skills/amber-chemist
diff -rq amber-chemist ~/.claude/skills/amber-chemist
```

[`PLAN.md`](PLAN.md) §"Sequencing rules" says wait until trigger
tests pass against dev before syncing — practically the order is
*edit dev → sync → test → fix in dev → sync → test* until clean.

---

## Development quickstart

```bash
# 0. Optional backends — install only what you need
pip install mace-torch                              # MACE (ase-chemist v1.2+)
conda install -c conda-forge ambertools             # Amber (both skills)
# Gaussian: license-gated; install per https://gaussian.com/

# 1. Sanity-check the simulation environments (both skills ship one)
python ase-chemist/scripts/check_env.py
python amber-chemist/scripts/check_env.py

# 2. Regenerate fixtures (caffeine.xyz, cluster.xyz, ar108.xyz, md.traj)
python generate_test.py

# 3. Run the 31-prompt trigger-test suite (17 ASE + 14 Amber)
bash run_tests.sh
TIMEOUT_SECS=300 bash run_tests.sh    # default 180s × 31 ≈ 90 min

# 4. Skim outcomes
for f in results/*.status; do
  printf "%-22s %s\n" "$(basename "$f" .status)" "$(cat "$f")"
done
```

The harness exits non-zero if any prompt timed out or errored.
Status values are `ok`, `timeout`, or `error:<rc>` (124/137 are GNU
`timeout` codes).

---

## How the trigger-test harness works

`run_tests.sh` runs **31 prompts** in fresh `claude -p` sessions with
a 180 s wall-clock cap each. Prompt IDs are namespaced by skill —
`p*` for `ase-chemist`, `a*` for `amber-chemist`. Each prompt is tagged:

- **`trigger`** — the skill should activate and produce a correct script.
- **`no_trigger`** — generic prompts that should not invoke the skill.
- **`borderline`** — definitional questions or graceful-deferral cases where either response is defensible; for human review.

`ase-chemist` coverage (17 prompts):

| Version | Prompts | Tests |
|---|---|---|
| v1.0 / v1.1 baseline | `p1`–`p5` (trigger), `p6`–`p7` (no_trigger), `p8`–`p9` (borderline) | xTB / EMT / LJ / TIP3P / build / analyze |
| v1.2 — MACE | `p10_mace_named`, `p11_size_cliff` (trigger) | foundation-model triggers, size-cliff method selection |
| v1.3 — Amber GAFF2 | `p12_gaff2_named`, `p13_antechamber` (trigger), `p14_protein_md` (borderline) | GAFF2 / antechamber triggers, v2.3 protein deferral |
| v1.4 — Gaussian DFT | `p15_gaussian_sp`, `p16_gaussian_freq` (trigger), `p17_dft_no_method` (borderline) | DFT triggers, no-defaults policy enforcement |

`amber-chemist` coverage (14 prompts, all v1.0):

| Area | Prompts | Tests |
|---|---|---|
| MD core | `a1_md_named`, `a2_extend`, `a4_implicit`, `a12_collision` (trigger) | named GAFF2 NPT, restart/extend, implicit GB, trigger-phrase collision with `ase-chemist` |
| T-REMD | `a3_remd`, `a5_demux`, `a11_remd_ladder`, `a14_remd_no_mpi` (trigger / borderline) | ladder, demux, ladder-tuning advice, no-MPI graceful deferral |
| Add-ons | `a6_mmpbsa`, `a7_alanine`, `a8_cpptraj`, `a9_esander` (trigger) | MMPBSA / alanine scan / cpptraj analysis / per-frame esander |
| Deferred features | `a10_ff19sb`, `a13_amd_borderline` (trigger / borderline) | ff19SB biopolymer deferral, aMD deferral |

The 180 s budget is intentionally too short to actually run a
simulation. The test asks *"did Claude write the right code?"*, not
*"did the code finish?"* — every prompt instructs the model not to
execute its output. Preserve that instruction when adding prompts.

`evals/evals.json` (one per skill) is a separate set of 5 richer
prompts with free-form expected outputs for **manual** review. v1 has
no programmatic assertions; that's [v2.0](PLAN.md)'s job.

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
- [`amber-chemist/references/`](amber-chemist/references/) — 15
  topic-scoped reference files (`md_core`, `remd`, `force_fields`,
  `analysis`, `scoring`, `failure_modes`, `extension_map`, …).

**Repo-level:**

- [`PLAN.md`](PLAN.md) — phase sequencing for v2 work on
  `ase-chemist`, the v2 vision proposal, and decisions deferred to
  usage data.
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
