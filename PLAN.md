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
- §3: caveat NPA charges — cclib's main attribute set does not include
  NPA; the cclib NBO parser is a separate dep. Drop NPA from v2 scope;
  the cclib NBO path is a v3 candidate.
- §3: add note that `ase.io.gaussian` does **not** parse vibrational
  frequencies. Any Freq workflow must use cclib.
- §4: mark "solvation defaults" → **answered: SMD** (~3–5 kcal/mol RMSD
  improvement over IEF-PCM for aqueous solvation free energies).
- §4: mark "cclib vs custom parser" → **answered: cclib** (v2 will
  depend on cclib for Freq/thermochem regardless).

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

- **Amber path: keep or remove?** v1.3 ships GAFF2 small-molecule MD via
  shell-out to AmberTools and pmemd. **Amber is the only engine in
  `ase-simulation` that does not run through ASE** (every other backend
  is wrapped as an ASE Calculator and driven in-process). The carve-out
  is forced — `ase.calculators.amber.Amber` is single-point only and
  rejects non-orthogonal cells, both fatal for MD — but it does break
  the "everything orchestrated through ASE" framing the rest of the
  skill maintains, and it doubles the surface area new contributors
  have to learn (mdin templates, antechamber pipeline, NetCDF I/O,
  engine-selection edge cases). **Decision criterion:** if usage data
  shows GAFF2 small-molecule MD is rarely requested (e.g., < ~5% of
  v1.3 invocations), the right call is to drop the v1.3 Amber path and
  tell users honestly that the skill doesn't ship a classical MM
  backend. If usage is heavy, the carve-out warts are worth keeping.
  Revisit at the same 2-week mark as the other usage-data questions.
- **ML**: molecules-vs-materials audience balance; system-size
  distribution; whether mandatory cross-validation overhead is
  acceptable; GPU prevalence among skill users.
- **Amber-GAFF2 (if kept)**: dominant ask (drug-like organics vs
  peptides vs carbohydrates); SLURM submission ownership; whether the
  skill should bundle equilibration protocols or always defer.
- **Gaussian** (v2.4 candidate): method/basis defaults for organics vs
  transition metals; resource defaults (`%mem`, `%nproc`); local vs
  queue submission.

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
