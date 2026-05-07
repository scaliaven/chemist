# v2 Implementation Plan

Working plan for the v2 surface of the `ase-simulation` skill, sequenced
on the `dev` branch. Inputs to this plan: the three v2 stubs landed in
commit `5716b7e` (2026-05-07) and the three subagent research reports
that followed.

The order is **stub corrections first**, then **ML potentials (MACE)**,
then **Amber-GAFF2 small-molecule MD**. Gaussian is deferred to v2.4 —
license barrier shrinks the audience and the "no defaults" stance
turns the skill into an input-deck typist rather than an orchestrator.

## Phase 0 — Stub corrections (1 commit, no code)

The existing stubs assert several things research surfaced as stale or
wrong. Land these fixes as one commit on `dev` *before* implementation
work, so the v2.1/v2.2 diffs stay focused on real changes.

### `references/amber.md`
- §1 / §3: replace `ff14SB`+TIP3P default with **`ff19SB`+OPC** for
  proteins, **`OL21`** for nucleic acids, **`GAFF2`** for small molecules.
- §1: drop the "paid Amber license for `pmemd.cuda`" caveat.
  AmberTools25 is fully open-source including `pmemd.cuda`.
- §2: add a hard note that `ase.calculators.amber.Amber` is **single-
  point only** (re-launches `sander` per `calculate()`, fatal for MD)
  and **rejects non-orthogonal cells** (kills truncated-octahedron
  solvation through the calculator path).
- §4: mark "ASE-Amber bridge vs shell-out" → **answered: shell-out**.
  Mark "default equilibration protocol" → **answered: min/heat/
  density/prod**.

### `references/gaussian.md`
- §3: caveat NPA charges — drop NPA from v2 scope; NBO output has
  its own format that would need its own parser; v3 candidate.
- §3: add note that `ase.io.gaussian` does **not** parse vibrational
  frequencies. The Freq workflow needs an in-house parser
  (`_gaussian_log.py`, ships in v1.4).
- §4: mark "solvation defaults" → **answered: SMD** (~3–5 kcal/mol RMSD
  improvement over IEF-PCM for aqueous solvation free energies).
- §4: mark "cclib vs custom parser" → **answered: in-house parser**.
  The skill maintains an "everything through ASE-or-our-own-code"
  framing; cclib is a third-party output parser layered on engines
  ASE already wraps. The `_gaussian_log.py` helper is ~100 lines of
  stdlib regex against Gaussian's stable .log format, with no extra
  install cost.

### `references/ml_potentials.md`
- §3: replace "MACE-MP-0 + CHGNet" with **"MACE-MP-0 (materials) +
  MACE-OFF (organics)"**. Same vendor, paired foundation models, single
  install (`pip install mace-torch`). CHGNet → v2.2.
- §3: revise size-cliff guidance — practical ceiling on a 40 GB A100 is
  **~1–2k atoms** with MACE medium, not 10k.
- §3: add explicit "mandatory cross-validation" subsection — every 1 ps
  of MD, recompute energy + force on the snapshot through GFN2-xTB
  (organics) or user reference (materials), abort at
  `MAE_F > 100 meV/Å`.
- §4: mark "which package dominant" → **answered: MACE**.
- §4: keep "molecules vs materials audience", "system size",
  "GPU assumption" open — these still need usage data.

## Phase 1 — ML potentials (MACE-MP-0 + MACE-OFF), v2.1

ML potentials live as real ASE `Calculator` instances (in-process, no
per-step subprocess). One factory function returns the right calculator
for the system; v1's `optimize.py` and `run_md.py` accept it through a
new `--calculator mace` flag. Cross-validation against GFN2-xTB is
mandatory by default for MD runs.

### Files

- **NEW** `scripts/ml_calculator.py` — `make_ml_calc(atoms, system_class,
  device)` factory. Auto-routes by element set: pure organic
  (H/C/N/O/P/S/F/Cl/Br/I) → `mace_off("medium")`, otherwise →
  `mace_mp("medium")`. `system_class` overrides routing. Device
  defaults to CUDA when available with a one-line CPU-fallback warning.

- **NEW** `scripts/validate_ml_md.py` — reads a trajectory, recomputes
  E/F at sampled frames through GFN2-xTB (organics) or a user-supplied
  reference, writes `validation.csv` (`step, MAE_E_meV,
  MAE_F_meV_per_A, max_F_dev_meV_per_A`). Aborts at
  `MAE_F > 100 meV/Å`.

- **MODIFY** `scripts/optimize.py` — add `--calculator mace` (alongside
  existing `xtb`/`emt`). When `mace`, calls `make_ml_calc(atoms)`.

- **MODIFY** `scripts/run_md.py` — add `--calculator mace`,
  `--validate-every <ps>` (default 1.0 for MACE; ignored otherwise),
  `--no-validate` to opt out.

- **MODIFY** `scripts/check_env.py` — promote MACE detection from
  `[v2 preview]` to a supported `[OK]`/`[MISSING]` block. Add
  `torch.cuda.is_available()` reporting plus device name + free VRAM.
  Surface a soft size-cliff warning. Other ML packages (CHGNet, M3GNet,
  SevenNet, Orb) stay in `[v2 preview]`.

- **REWRITE** `references/ml_potentials.md` — from stub to reference.
  §1 method-selection rules, §2 cross-validation contract, §3 known
  failure modes (liquid mixtures, ~1–2k atom ceiling), §4 GPU/CPU
  performance, §5 troubleshooting. Open questions move to PLAN.md
  Phase 3.

- **MODIFY** `SKILL.md` — add MACE to method-selection tree, gated on
  the size cliff (~1k atoms or ~10 ps of xTB MD). Add trigger phrases:
  "MACE", "MACE-OFF", "ML potential", "foundation model", "speed up
  this MD", "run a 10k-atom system".

- **MODIFY** `README.md` — move ML potentials from "What's coming in
  v2" to "What's in v1.2". Note `mace-torch` as an optional install.

### Deferred to v2.2

CHGNet for charge-aware materials; Orb-v3 confidence-head OOD signal;
committee-uncertainty heads on a frozen MACE backbone.

## Phase 2 — Amber (GAFF2 small-molecule MD), v2.2

Scope is **GAFF2 only** — small-molecule MD via antechamber AM1-BCC
charges + GAFF2 force field + tleap solvation + pmemd MD. Protein and
nucleic-acid MD (ff19SB/OPC, OL21) defers to v2.3. This focused scope
matches v1's existing organic / main-group emphasis.

Architecture is shell-out, not ASE-Calculator. The skill writes input
decks (`tleap.in`, `mdin`), invokes engines (`antechamber`, `parmchk2`,
`tleap`, `pmemd`/`pmemd.cuda`/`sander`), parses outputs, hands the
trajectory to v1's `analyze_traj.py`. ASE handles structure I/O at the
boundaries only.

### Files

- **NEW** `scripts/parameterize_gaff2.py` — input is a structure
  (`.pdb`, `.mol2`, `.sdf`, `.xyz` with explicit charge/multiplicity).
  Pipeline: `antechamber -fi <fmt> -fo mol2 -c bcc -s 2 -nc <q>` →
  `parmchk2` → `tleap` (load gaff2, solvate `solvateBox TIP3PBOX 12.0`
  or OPC, `addions Na+ 0`, `saveAmberParm`, `savePdb`). Outputs
  `<basename>.prmtop`, `<basename>.rst7`, `<basename>_solvated.pdb`.

- **NEW** `scripts/run_amber.py` — input is `.prmtop` + `.rst7` (BYO or
  from `parameterize_gaff2.py`). Stage flags: `--protocol standard`
  runs all four; `--stage min|heat|density|prod` for granular use.
  Stage templates rendered into `mdin`:
    - `min`: `imin=1, maxcyc=10000, ntmin=1, ncyc=5000`
    - `heat`: 50 ps NVT, `ntt=3, gamma_ln=2.0, tempi=0, temp0=300`
    - `density`: 100 ps NPT, `ntp=1`
    - `prod`: configurable `nstlim`, NPT default
  Engine selection: `pmemd.cuda` if GPU detected and binary present;
  else `pmemd`; else `sander`. Print engine line so users can override.
  Outputs NetCDF `.nc`, `mdout` for parsed scalars, final `.rst7`.

- **MODIFY** `scripts/check_env.py` — promote Amber detection from
  `[v2 preview]` to supported `[OK]`/`[MISSING]`. Detect
  `antechamber`, `parmchk2`, `tleap`, `sander`, `pmemd`, `pmemd.cuda`.
  Capability summary adds "small-molecule MD with GAFF2" when both
  AmberTools binaries (antechamber + tleap) and at least one MD engine
  resolve.

- **REWRITE** `references/amber.md` — from stub to GAFF2-focused
  reference. §1 GAFF2 small-molecule pipeline, §2 force-field choices
  (GAFF2 vs GAFF, AM1-BCC vs RESP), §3 solvation (TIP3P vs OPC),
  §4 engine selection, §5 known failure modes (non-orthogonal cells,
  partial charges that fail antechamber), §6 troubleshooting. Note
  that protein/NA MD is deferred to v2.3.

- **MODIFY** `SKILL.md` — add Amber-GAFF2 to method-selection tree
  (small organic in explicit solvent + production MD → GAFF2 when
  AmberTools present; small organic in vacuum or implicit solvent →
  GFN2-xTB as before). Trigger phrases: "GAFF2", "explicit-solvent
  MD", "ligand MD", "small-molecule MD in water", "Amber",
  "antechamber".

- **MODIFY** `README.md` — move Amber-GAFF2 from "What's coming in v2"
  to "What's in v1.3". Note that protein/NA MD is still v2.3.

### Deferred to v2.3

Protein MD with ff19SB/OPC; nucleic-acid MD with OL21; full
tleap-from-PDB system prep for biomolecules; multi-GPU pmemd.cuda.

## Phase 3 — Decisions deferred to usage data

These come from the original §4 stub questions plus subagent flags.
Update PLAN.md as each lands or as data arrives.

- **Amber path: keep, switch to SANDER+ASE, or remove?** v1.3 ships
  GAFF2 small-molecule MD via shell-out to AmberTools and pmemd.
  **Amber is the only engine in `ase-simulation` that does not run
  through ASE** (every other backend is wrapped as an ASE Calculator
  and driven in-process). The carve-out was a **performance choice,
  not forced** — `ase.calculators.amber.SANDER` (pysander Python
  bindings, in-process, no subprocess per step) would let ASE drive
  the MD loop coherently. v1.3 declined that path because pysander
  binds only to CPU sander (no pmemd.cuda); on a typical 5k-atom
  system, the whole min/heat/density/500-ps-prod protocol is hours
  via SANDER vs. minutes via pmemd.cuda. The shell-out also doubles
  the surface area new contributors have to learn (mdin templates,
  antechamber pipeline, NetCDF I/O, engine-selection edge cases).
  **Four options:**
    1. *Keep pmemd shell-out (current).* Production-fast, GPU-accelerated;
       accept the architectural carve-out.
    2. *Switch to `SANDER` + ASE Langevin.* Architecturally clean;
       accept CPU-only and ~10–50× slowdown. Becomes attractive if most
       users don't actually have a GPU, or if their typical run is short
       enough that wall-clock difference is acceptable.
    3. *Remove Amber entirely.* Tell users honestly that the skill
       doesn't ship a classical MM backend.
    4. *Build the missing API path.* Write a proper ASE Calculator
       around `pmemd` / `pmemd.cuda` so the wrapper is ASE-shaped and
       still hits pmemd.cuda speed. Two sub-shapes: (a) long-lived
       pmemd subprocess where ASE owns setup/teardown but pmemd owns
       the integration loop — wraps cleanly at the script level even
       though per-step E/F isn't exposed; (b) contribute `pmemd` /
       `pmemd.cuda` Python bindings upstream so a future `PMEMD` class
       in `ase.calculators.amber` can bind them the way `SANDER` binds
       pysander. Most engineering work of the four; only option that
       gets both ASE-coherence and pmemd.cuda throughput.
  **Decision criterion:** usage frequency × GPU prevalence × typical
  run length × engineering capacity. If GAFF2 use is rare (< ~5% of
  v1.3 invocations), pick (3). If it's common but most users are
  GPU-less or run short trajectories, pick (2). If it's common, users
  want production-length runs at scale, **and** there's appetite to
  invest in a wrapper, pick (4). Otherwise (1) holds — the carve-out
  is the tax for production speed without engineering work.
- **ML**: molecules-vs-materials audience balance; system-size
  distribution; whether mandatory cross-validation overhead is
  acceptable; GPU prevalence among skill users.
- **Amber-GAFF2 (if kept)**: dominant ask (drug-like organics vs
  peptides vs carbohydrates); SLURM submission ownership; whether the
  skill should bundle equilibration protocols or always defer.
- **Gaussian extended scope (v3+)**: should `Opt=TS` / IRC / NBO+NPA /
  post-HF / TDDFT land? v1.4 deliberately ships SP/Opt/Freq/SMD only.
  Each extension has its own design problem (TS needs Hessian-guess +
  IRC; NPA needs an NBO-output parser of its own; post-HF needs
  basis-set/disk heuristics). Decision criterion: usage data showing
  which extension has the loudest demand.
- **Gaussian queue submission**: v1.4 runs locally only. SLURM
  templates may land in v2.5+; for now users wrap `gaussian_*.py` in
  their own queue script.

## Vision for v2 (proposal — not yet ratified)

This section is an opinionated forward look, written 2026-05-08
after v1.4 landed. It supersedes the earlier "v2.2+ → v2.4 → v3+"
sequencing implied above when the two disagree, but Phase 3 open
questions stay the same. If the user picks a different shape, edit
this section and re-anchor the milestones.

### Where v1.x actually landed

**Strong**

- The ASE-as-orchestrator pattern works for SCF codes (Gaussian,
  tblite) and in-process Python calculators (EMT, LJ, MACE).
- The MACE cross-validation contract is genuinely load-bearing — it
  is the difference between "we ship MACE" and "we ship MACE
  honestly."
- The Phase A reference split (commit `952c5fd`, 2026-05-08) gave
  the model granular navigation across the three big chapters.

**Weak**

- The skill ships seven backends (EMT / LJ / TIP3P / xTB / MACE /
  Gaussian / Amber-GAFF2) but has never run a real end-to-end job.
  v1.2/v1.3/v1.4 are all "code-correct" — they parse `--help` and
  have plausible-looking control flow, but no one has actually
  finished a MACE MD with the validation firing, or a real Gaussian
  Freq, or a GAFF2 ligand simulation. Every integration is on a
  trust-me footing.
- Evals are still 5 v1.0 prompts with no programmatic assertions.
- SKILL.md is ~22k chars after v1.4 and still grows every release.
- The Amber carve-out has four open options and no resolution.

### Thesis

**v1.x was about feature breadth. v2 should be about earning what we
built and learning to compose it.** Not "add more engines."

The user value of "we have N backends" is much smaller than "you can
use them together with confidence." Three backends in a working
ladder beat seven that don't compose.

### Milestones

**v2.0 — Architectural cleanup. No new backends.**

- **Resolve the Amber carve-out.** Pick one of the four options
  (Phase 3 above). Driven by usage data when available; by
  engineering capacity when not — option (4) if there is appetite to
  build a proper pmemd ASE Calculator, option (3) if not.
- **Phase B of the navigation refactor**: slim SKILL.md by moving
  inline rationale into the v1.4 sub-references. Phase A (the
  reference split) gave a clean target for this. Net result: SKILL.md
  ~22k → ~12k chars, sub-references hold the multi-paragraph "Why:"
  blocks and architecture-note callouts.
- **End-to-end integration tests on a tight benchmark**: HF/STO-3G
  H₂O Gaussian SP, 1 ps caffeine xTB MD, MACE optimization with
  cross-validation actually firing, GAFF2 minimization on a small
  ligand. Each one comes back as `[OK]` or the version's claim is
  fixed. This earns v1.x's feature claims through real testing
  instead of trust-me.
- **Programmatic assertions** added to `evals/evals.json` (file
  presence, energy ranges, drift signs). PLAN.md has been calling
  this iteration-2's job since v1.0; v2.0 ships it.

**v2.1 — Composition primitives.**

- A bundled **method-ladder** script: optimize cheap (xTB), refine
  expensive (DFT). One CLI, not three glued together.
- A generic **cross-validation primitive**, separated from MACE-
  specific code. CHGNet / Orb (v2.2) inherit it for free instead of
  re-implementing.
- A **workflow registry** at `scripts/workflows/` for repeatable
  protocols: binding energy with mixed methods; conformer search
  → DFT refine; multi-stage MD ladders.

**v2.2 — More ML potentials, riding the v2.1 cross-validation primitive.**

- CHGNet for charge-aware materials (battery cathodes, oxidation
  states).
- Orb-v3 with its built-in confidence head for richer OOD signal.
- Both inherit the generic cross-validation contract; no MACE-style
  bespoke wiring.

**v2.3 — Biomolecular Amber.**

- ff19SB + OPC for proteins; OL21 for nucleic acids.
- Full tleap-from-PDB pipeline (pdb4amber, disulfide handling,
  capping).
- Architecture inherits whatever v2.0 picked for the carve-out.

**v2.4 — HPC submission.**

- SLURM templates / queue-aware wrappers.
- Restart logic.
- Pure UX, no architecture changes. Useful only if v2.0 + v2.1
  landed first.

**v3+ — Research-y extensions.**

- Gaussian: TS / IRC / NBO+NPA / post-HF (CCSD/MP2/CASSCF) /
  TDDFT / anharmonic.
- Free energy (TI / FEP / MBAR), enhanced sampling (REMD /
  metadynamics / umbrella sampling).
- VASP / QE / community-code bridges (CP2K, FHI-aims).
- Each is its own design pass with its own validation suite. None
  belong in v2.

### Open questions to resolve before v2.0 starts

1. **Is "earn before extend" the right v2 thesis?** The alternative
   is the original PLAN.md path — keep adding engines (CHGNet →
   Amber-protein → Gaussian extensions). That ships features faster
   but compounds the untested-integration debt. Pick before v2.0
   begins.
2. **Composition or polishing first?** v2.0 (cleanup + earn what's
   built) is unsexy but probably highest value. v2.1 (composition)
   is the more interesting work. They could swap order if "build
   first, clean up after" is a better fit for the team.
3. **Is the Amber carve-out worth resolving in v2.0, or live with
   it indefinitely?** Honestly, it could just stay open as a flagged
   carve-out. The four options are all defensible; declining to pick
   is also a valid choice.

## Sequencing rules

- Don't sync to `.claude/skills/ase-simulation/` until a phase's
  trigger tests pass against the dev source. Mid-phase syncs change
  the live trigger surface and contaminate in-flight test runs.
- Each phase ends with a single commit on `dev` and a re-run of
  `bash run_tests.sh`. If trigger reliability regresses, fix in the
  same phase, not the next.
- Phase 1 (ML) ships before Phase 2 (Amber-GAFF2). They are
  sequenced, not parallel — overlapping diffs through `check_env.py`
  and `SKILL.md` would be hard to bisect.
