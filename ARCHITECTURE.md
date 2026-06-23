# Architecture: skills vs. agents vs. MCP — an honest take

## Context

Right after an audit that surfaced doc/code drift (SKILL.md flags vs. argparse) and
duplication (the Amber pipeline copied across both skills), you asked whether the whole
thing might be better as "2 skill sets, or agents, or MCP and stuff." You want a
clear-eyed read on the *paradigm*, not a committed migration — distribution beyond
Claude Code is not (yet) a requirement.

This file is a decision memo, not an implementation task. It records the recommendation
and a concrete (optional) refactor that follows from it.

## What this repo actually is

A **method-selection expert system** for atomistic simulation. The hard-won value is the
*judgment*, expressed as natural-language decision trees:
- "EMT silently lies on organics — never substitute it."
- "Cross-validate MACE against GFN2-xTB every 1 ps or it produces plausible-wrong PESs."
- "Refuse Gaussian without explicit method/basis/charge/mult."

Underneath that judgment sits a thin layer of **execution primitives** (optimize, run_md,
single_point, render mdin, parse logs) that shell out to ASE / tblite / MACE / AmberTools
/ Gaussian.

The project's current trajectory is *more sibling skills*: `PLAN.md` §Phase 3 deliberately
chose (2026-05) to keep the Amber shell-out and ship `amber-chemist` as a sibling, and
`OPENMM_PROPOSAL.md` proposes a **third** sibling (`openmm-chemist`) for GPU-resident ML/MM.

## The honest take: it's a false trichotomy — these are layers, not alternatives

Skills, subagents, and MCP solve different layers. Mapping them to this project:

**Layer 1 — intelligence + triggering (the decision trees + the `description` trigger
contract). This MUST stay a Skill.**
- A skill is "expertise injected into Claude's context; the model decides what to do." The
  entire value here is the model picking the method. That is the skill's core competency.
- MCP cannot express it: an MCP tool is a typed function; it can't encode "if d-block and
  GFN2 fails to converge, fall back to GFN1." That's reasoning, not a schema.
- A subagent has a system prompt but **does not auto-trigger** on user phrasing. The
  enumerated-phrase `description` field ("relax this molecule", "thermalize at 300 K") that
  makes the skill activate is a skill-only mechanism — you'd lose automatic activation.
- **Converting Layer 1 to agents or MCP is strictly worse.**

**Layer 2 — execution (the scripts). This is where the pain is, and the pain is
duplication, not the paradigm.**
- Today each skill bundles its own `scripts/`. The Amber pipeline exists **twice** with no
  shared code, and has **already drifted** (evidence below).
- Three possible homes: (a) bundled scripts = status quo, duplication scales with #skills;
  (b) a shared Python package both skills import = kills duplication + a class of drift, no
  new infra; (c) an MCP server = the package exposed with typed schemas + statefulness.

**The decision is only about Layer 2's home — and nothing you have today justifies (c).**
MCP buys cross-client reuse (you don't need it), enforced input validation (nice, not
urgent), and a natural home for warm GPU-resident models / long-lived `pmemd.cuda` (a real
future perf win, but not a stated pain). And even with MCP you *still need the skill* for
Layer 1. So MCP is deployment overhead for no current gain.

## Evidence: the duplication is the bug, and it's live

- `ase-chemist/scripts/run_amber.py:84-150` defines its **own** `render_min/heat/density/
  prod`, completely separate from `amber-chemist/scripts/_amber.py`. There is **no shared
  module** — `ase-chemist/scripts/` has no `_amber.py`; the only shared helpers are `_calc.py`
  and `_gaussian_log.py`.
- The two copies have **already diverged**. This session I fixed a density-restart bug in
  `amber-chemist/scripts/_amber.py` (added an `irest` flag instead of hardcoding
  `irest=1, ntx=5`). The ase-chemist copy at `run_amber.py:118` **still hardcodes
  `irest=1, ntx=5`** — the fix didn't propagate, because nothing connects them.
- The carve-out is ~580 lines (`parameterize_gaff2.py` 277 + the `run_amber.py` renderers/
  driver) reimplementing a frozen subset of `amber_prep.py` + `_amber.py` + `amber_md.py`.
- Same root cause as the audit's SKILL.md-vs-argparse drift: **the contract is written down
  twice and the copies fall out of sync by hand.**

## Recommendation

1. **Keep skills as the trigger + method-selection layer.** Do not convert to agents or MCP
   at this layer. This is the load-bearing value and the thing the paradigm does best.

2. **Fix Layer 2's duplication — this is the highest-leverage move and it's paradigm-
   neutral.** Extract a shared execution core (start with the Amber pipeline) so the
   carve-out stops being a second copy. This directly attacks the audit's root cause and is
   also the prerequisite that makes any *future* MCP/agent layer cheap: you'd wrap the core,
   not rewrite it.

3. **Make SKILL.md stop hand-describing flags.** The per-script bullets that enumerate
   `--rst`/`--net-charge`/`--convergence` are a drift generator. Point at `script --help` or
   a generated reference; keep prose for *judgment* (when to reach for each), not for the
   arg list.

4. **Treat MCP and subagents as optional future wrappers, gated on concrete drivers you
   don't have yet:**
   - **MCP** when (a) you want these tools usable outside Claude Code, or (b) you want warm
     GPU-resident MACE / long-lived `pmemd.cuda` (the `PLAN.md` Phase-3 option-4 perf gap).
     It wraps the shared core from step 2.
   - **Subagents** when verbose simulation output (mdout tails, validation CSVs, optimizer
     logs) starts cluttering the main thread — a `chemistry-runner` subagent absorbs the run
     and returns just the conclusion. Cheap, orthogonal, not urgent.

5. **On sibling-skill proliferation (2 → 3 with OpenMM):** the per-engine-idiom split is
   defensible — each engine has its own mental model and restart format (`.rst7` vs
   `state.xml`). The real scaling risk is **trigger-contract competition**: ase-, amber-, and
   openmm-chemist will all want "MD on my ligand in water." That's a `description`-field
   (Layer 1) problem, solved by sharpening routing, **not** by restructuring into MCP/agents.

## What I would *not* do

- Convert either skill into an MCP server or a subagent now — no driver, and Layer 1 would
  still need a skill anyway.
- Merge the two skills into one — the engine-idiom split is sound; merging would bloat one
  `description` field and *hurt* trigger reliability (the load-bearing thing).
- Build the `pmemd.cuda` ASE-Calculator / warm-model statefulness now — that's a real but
  deferred perf project (`PLAN.md` Phase 3, option 4), not part of this rethink.

## Concrete next steps (only if you want to act on #2/#3)

Phased, lowest-risk first:
- **Phase A — dedupe Amber.** Make `ase-chemist`'s carve-out import from a single source of
  truth instead of re-implementing renderers. Options: (i) a small shared package both
  skills depend on; (ii) `ase-chemist` re-exports a thinned subset of `amber-chemist/scripts/
  _amber.py`. Either way, one set of renderers. Re-apply the `irest` fix once, centrally.
- **Phase B — thin the docs.** Replace per-script flag enumerations in both `SKILL.md`s with
  "reach for it when …" prose + a pointer to `--help`. Add a tiny check (or generation step)
  that the documented flags exist, so drift is caught mechanically.
- **Phase C — (optional, deferred) MCP wrapper** over the shared core, only when a
  distribution or warm-state driver appears.

## Verification

The skills' contract is *trigger behavior*, so any refactor is verified the same way the
repo already verifies itself:
- `python ase-chemist/scripts/check_env.py` still summarizes capabilities.
- `bash run_tests.sh` — the 14-prompt trigger/no-trigger/borderline harness — must show no
  regression in activation or method selection (this is the real safety net for touching
  skills; `PLAN.md` §"Sequencing rules" treats it as the gate).
- For Phase A specifically: `python -c "import _amber; _amber.render_density(...)"` parity
  between what each skill emits, plus a one-time diff to confirm the `irest` fix is now
  single-sourced.
- Remember the three-copy model: after editing dev source, `rsync` into `.claude/skills/`
  and `~/.claude/skills/` before the harness (it loads the copies, not the dev tree).

---

**Bottom line:** the paradigm is right — skills are the correct primitive for a
method-selection expert system, and "agents or MCP instead" would be a downgrade for the
part that matters. The thing worth fixing is the *duplication* the audit exposed: extract a
shared execution core and stop writing the contract down twice. MCP and subagents are
future *wrappers* around that core, not replacements for the skills — adopt them only when a
concrete driver (cross-client reuse, warm GPU state, context-pollution) actually shows up.
