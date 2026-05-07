# chemist

> A development workspace for an Agent Skill that takes computational
> chemistry seriously: documented method selection over feature-list
> mentality, honest limits over silent fallbacks, mandatory cross-
> validation over *"just trust the ML potential."*

`chemist` is the dev workspace for [`ase-chemist`](ase-chemist/),
a Claude Code skill for atomistic / molecular simulation. The skill
bundles seven backends (ASE built-ins, tblite-xTB, MACE foundation
models, Amber-GAFF2, Gaussian DFT) behind one method-selection router,
and ships a 17-prompt regression suite that runs trigger / no-trigger
prompts through `claude -p` to catch activation and method-selection
drift between releases.

This is **not** an application — there's no library to import and no
service to run. Working here means editing the skill, regenerating
test fixtures, syncing the loaded copies, and shipping commits on
`dev`. v2 sequencing is tracked in [`PLAN.md`](PLAN.md).

---

## Why this project might be worth a read

Computational-chemistry tooling tends toward two failure modes:
*"here are 50 tools, you figure it out"* (every general-purpose ASE
script) and *"here's a black box, give me your structure"* (every
opinionated wrapper). `ase-chemist` lands between them on a
specific design rigor:

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
   `references/amber_carveout.md` and under review.

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
[`ase-chemist/README.md`](ase-chemist/README.md).

---

## Layout

```
chemist/
├── ase-chemist/                  # the skill itself (dev source — edit here)
│   ├── SKILL.md                     # trigger contract + method-selection tree
│   ├── README.md                    # the skill's user-facing README
│   ├── scripts/                     # 12 scripts (one per task)
│   ├── references/                  # 17 small scoped reference files
│   └── evals/evals.json             # 5 prompts for manual review
├── .claude/skills/ase-chemist/   # project skill copy (loaded by `claude -p`)
├── ~/.claude/skills/ase-chemist/ # user skill copy (kept in parity)
├── PLAN.md                          # v2 vision + phase sequencing
├── CLAUDE.md                        # design decisions for Claude Code sessions
├── generate_test.py                 # fixture generator
├── run_tests.sh                     # trigger-test harness (17 prompts, v1.0 → v1.4)
├── test-inputs/                     # generated fixtures (gitignored)
└── results/                         # per-run logs + .status (gitignored)
```

The dev source under `ase-chemist/` and the loaded copies under
`.claude/skills/` and `~/.claude/skills/` can drift. Tests run
against the loaded copies. Sync after every edit:

```bash
rsync -a --delete ase-chemist/ .claude/skills/ase-chemist/
rsync -a --delete ase-chemist/ ~/.claude/skills/ase-chemist/
diff -rq ase-chemist .claude/skills/ase-chemist     # confirm parity
diff -rq ase-chemist ~/.claude/skills/ase-chemist
```

[`PLAN.md`](PLAN.md) §"Sequencing rules" says wait until trigger
tests pass against dev before syncing — practically the order is
*edit dev → sync → test → fix in dev → sync → test* until clean.

---

## Development quickstart

```bash
# 0. Optional backends — install only what you need
pip install mace-torch                              # MACE (v1.2+)
conda install -c conda-forge ambertools             # Amber GAFF2 (v1.3+)
# Gaussian: license-gated; install per https://gaussian.com/

# 1. Sanity-check the simulation environment
python ase-chemist/scripts/check_env.py

# 2. Regenerate fixtures (caffeine.xyz, cluster.xyz, ar108.xyz, md.traj)
python generate_test.py

# 3. Run the 17-prompt trigger-test suite
bash run_tests.sh
TIMEOUT_SECS=300 bash run_tests.sh    # default 180s × 17 ≈ 50 min

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

`run_tests.sh` runs **17 prompts** in fresh `claude -p` sessions with
a 180 s wall-clock cap each. Each prompt is tagged:

- **`trigger`** — the skill should activate and produce a correct ASE script.
- **`no_trigger`** — generic prompts that should not invoke the skill.
- **`borderline`** — definitional questions or graceful-deferral cases where either response is defensible; for human review.

Coverage by version:

| Version | Prompts | Tests |
|---|---|---|
| v1.0 / v1.1 baseline | `p1`–`p5` (trigger), `p6`–`p7` (no_trigger), `p8`–`p9` (borderline) | xTB / EMT / LJ / TIP3P / build / analyze |
| v1.2 — MACE | `p10_mace_named`, `p11_size_cliff` (trigger) | foundation-model triggers, size-cliff method selection |
| v1.3 — Amber GAFF2 | `p12_gaff2_named`, `p13_antechamber` (trigger), `p14_protein_md` (borderline) | GAFF2 / antechamber triggers, v2.3 protein deferral |
| v1.4 — Gaussian DFT | `p15_gaussian_sp`, `p16_gaussian_freq` (trigger), `p17_dft_no_method` (borderline) | DFT triggers, no-defaults policy enforcement |

The 180 s budget is intentionally too short to actually run a
simulation. The test asks *"did Claude write the right code?"*, not
*"did the code finish?"* — every prompt instructs the model not to
execute its output. Preserve that instruction when adding prompts.

`evals/evals.json` is a separate set of 5 richer prompts with
free-form expected outputs for **manual** review. v1 has no
programmatic assertions; that's [v2.0](PLAN.md)'s job.

---

## Project documentation

- [`ase-chemist/README.md`](ase-chemist/README.md) — the
  skill's user-facing README. Backends, examples, design principles,
  install. **Read this first if you want to understand what the
  skill does.**
- [`ase-chemist/SKILL.md`](ase-chemist/SKILL.md) — the trigger
  contract (description field), method-selection tree, scripts
  catalog. Editing the description field regresses or improves
  activation; treat it as load-bearing.
- [`ase-chemist/references/`](ase-chemist/references/) — 17
  small scoped reference files (1–4k chars each). The umbrella files
  (`ml_potentials.md`, `amber.md`, `gaussian.md`) are thin indices
  that point at sub-files for the specific topic — read only the
  one that matches your task.
- [`PLAN.md`](PLAN.md) — phase sequencing for v2 work, the v2 vision
  proposal, and decisions deferred to usage data.
- [`CLAUDE.md`](CLAUDE.md) — load-bearing design decisions for
  Claude Code sessions working in this repo. The skill-copy
  duplication rules, the load-bearing carve-outs, the
  what-NOT-to-touch list.
