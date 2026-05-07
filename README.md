# asechemist

Development workspace for the **`ase-simulation` Agent Skill** — a Claude Code
skill that orchestrates atomistic simulations (MD, geometry optimization,
vibrational analysis, NEB, structure building) on top of ASE, tblite-xTB, EMT,
and TIP3P.

This repo is **not** an application. There is no library to import and no
service to run. Working here means editing the skill, regenerating test
fixtures, and re-running the trigger-test harness to check that changes
don't regress activation or method-selection behavior.

## Layout

```
asechemist/
├── ase-simulation/                  # skill dev source (edit here)
│   ├── SKILL.md, README.md
│   ├── scripts/    check_env.py, optimize.py, run_md.py, single_point.py, analyze_traj.py
│   ├── references/ ase_core.md, xtb.md, analysis.md
│   └── evals/evals.json
├── .claude/skills/ase-simulation/   # project-scoped copy loaded by `claude -p` (gitignored; produced via rsync — see below)
├── generate_test.py                 # fixture generator
├── run_tests.sh                     # trigger-test harness
├── test-inputs/                     # generated fixtures (gitignored)
└── results/                         # per-run logs + .status (gitignored)
```

> The dev source under `ase-simulation/` and the loaded copy under
> `.claude/skills/ase-simulation/` can drift. Tests run against the loaded
> copy. Sync after edits:
>
> ```bash
> rsync -a --delete ase-simulation/ .claude/skills/ase-simulation/
> diff -rq ase-simulation .claude/skills/ase-simulation   # confirm parity
> ```

## Quickstart

```bash
# 1. Sanity-check the simulation environment
python ase-simulation/scripts/check_env.py

# 2. Regenerate fixtures (caffeine.xyz, cluster.xyz, ar108.xyz, md.traj)
python generate_test.py

# 3. Run the trigger-test suite (writes results/<id>.{log,status})
bash run_tests.sh

# longer per-prompt budget
TIMEOUT_SECS=300 bash run_tests.sh

# 4. Skim outcomes
for f in results/*.status; do
  printf "%-22s %s\n" "$(basename "$f" .status)" "$(cat "$f")"
done
```

The harness exits non-zero if any prompt timed out or errored. Status values
are `ok`, `timeout`, or `error:<rc>` (124/137 are GNU `timeout` codes).

## What the test harness does

`run_tests.sh` runs nine prompts in fresh `claude -p` sessions with a 180 s
wall-clock cap each, tagged as one of:

- **`trigger`** — the skill should activate and produce a correct ASE script.
- **`no_trigger`** — generic prompts that should not invoke the skill.
- **`borderline`** — definitional questions where either is defensible; for
  human review.

The 180 s budget is intentionally too short to actually run a simulation.
The test asks "did Claude write the right code?", not "did the code finish?"
— every prompt instructs the model not to execute its output. Preserve that
when editing prompts.

`evals/evals.json` is a separate set of five richer prompts with free-form
expected outputs for **manual** review. v1 has no programmatic assertions;
adding stable ones is iteration 2's job.

## Skill design

See [`ase-simulation/README.md`](ase-simulation/README.md) for install,
backends, and v2 scope. See [`CLAUDE.md`](CLAUDE.md) for the load-bearing
design decisions (method selection, why `tblite` is preferred over
`xtb-python`, what's intentionally out of v1) and what to preserve when
editing.
