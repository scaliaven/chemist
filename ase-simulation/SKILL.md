---
name: ase-simulation
description: Use this skill whenever the user wants to run, set up, or analyze atomistic simulations on molecules or materials. This covers: molecular dynamics (MD, NVE, NVT, NPT, Langevin, Nose-Hoover) including thermalization, equilibration, and "warm up the system" requests; geometry optimization, energy minimization, or relaxation (BFGS, FIRE, LBFGS — "minimize this molecule", "relax this structure", "find the equilibrium geometry"); vibrational frequency, normal-mode, Hessian, and zero-point-energy analysis; NEB and transition-state searches; structure building (small molecules, bulk crystals, surfaces like fcc111, slabs with adsorbates); trajectory analysis (RMSD, RMSF, RDF, energy drift); single-point energy and force evaluation; binding, interaction, and adsorption energy calculations; explicit-solvent small-molecule MD with GAFF2 + AM1-BCC charges via antechamber and pmemd; **DFT calculations via Gaussian — single-point energies, geometry optimization, frequency / thermochemistry analysis (ZPE, enthalpy, Gibbs free energy)** with B3LYP / ωB97X-D / M06-2X / PBE0 etc.; and electronic observables like HOMO-LUMO gap, dipole moment, or Mulliken charges. Use this skill for any request involving force fields (GAFF2, AM1-BCC, classical MM), semi-empirical methods (xTB / GFN1 / GFN2), foundation-model ML potentials (MACE-MP-0, MACE-OFF), DFT through Gaussian (B3LYP, ωB97X-D, M06-2X, PBE0, def2-TZVP, 6-31G(d), SMD/PCM solvation), DFT-style reasoning about which method to pick, or any computational chemistry / materials task that mentions ASE, EMT, Lennard-Jones, TIP3P, tblite, xtb, MACE, antechamber, tleap, sander, pmemd, Gaussian, g16, g09, or cclib. Reach for this skill even when the user does not name ASE — phrases like "minimize this molecule", "relax this geometry", "thermalize at 300 K", "equilibrate the system", "compute the binding energy", "run MD on water", "build a Pt(111) slab", "compute frequencies", "speed up this MD with a foundation model", "use MACE", "run a 5000-atom system", "ligand MD in water", "GAFF2 parameterization", "AM1-BCC charges", "explicit-solvent MD of this drug molecule", "antechamber", "run a DFT calculation", "compute thermochemistry at B3LYP/def2-TZVP", "Gibbs free energy of this reaction", "Gaussian SMD water", or "DFT frequency analysis" should all trigger this skill.
license: MIT
---

# ASE Simulation Skill (v1.4)

## Always do this first

Before any non-trivial task, run:

```bash
python scripts/check_env.py
```

It prints which calculators and analysis tools are actually installed, and
ends with a one-line "what you can run right now" summary. **Recommend a
method that the environment supports** — do not ask the user to install xTB if
EMT or LJ already covers the question.

If a backend is missing and the user wants it, prefer the conda install on
HPC / conda systems:

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib
```

…and pip only when conda isn't available:

```bash
pip install ase tblite mdanalysis matplotlib
```

For MACE foundation-model support (v1.2+), install separately:

```bash
pip install mace-torch
```

`tblite` ships GFN1-xTB and GFN2-xTB and is the supported successor to the
deprecated `xtb-python`. If `check_env.py` reports `[BROKEN] tblite ...
C extension unloadable`, the pip wheel is libgfortran-incompatible — switch
to `conda install -c conda-forge tblite-python`. The standalone `xtb`
binary (Grimme group) adds GFN0 and GFN-FF if it's on PATH.

`mace-torch` provides the **MACE-MP-0** (89-element materials/inorganic
foundation model) and **MACE-OFF** (10-element organics foundation
model) calculators. Together they cover the systems where GFN2-xTB
runs out of speed (~1k+ atoms). MACE requires `torch`; CUDA is
strongly recommended (CPU mode is ~10× slower and the practical size
ceiling halves). `check_env.py` reports CUDA status and a soft size-
cliff warning based on free VRAM.

## Method selection

Walk these three steps in order. Each rule names *what* to do and *why*; if
the user's case doesn't fit the "because", the rule probably doesn't apply
and you should keep walking.

### Step 1 — what task is this?

| Task | Tool | Notes |
|---|---|---|
| Optimize / minimize / relax | `scripts/optimize.py` | FIRE for far-from-equilibrium, BFGS otherwise |
| MD at temperature T | `scripts/run_md.py` | Langevin NVT is the default ensemble |
| Production explicit-solvent MD on a small organic | `scripts/parameterize_gaff2.py` then `scripts/run_amber.py` | GAFF2 + AM1-BCC, TIP3P/OPC water, min/heat/density/prod via pmemd. See `references/amber.md` |
| **DFT single-point** (energy / forces / dipole / charges at DFT level) | `scripts/gaussian_sp.py` | wraps `ase.calculators.gaussian.Gaussian`; cclib for charges/MO. **No method/basis defaults — refuse without `--method`/`--basis`/`--charge`/`--mult`/`--mem`/`--nproc`.** |
| **DFT geometry optimization** | `scripts/gaussian_opt.py` | uses `GaussianOptimizer` (Gaussian L103 — much faster than ASE-BFGS-around-Gaussian-SP). `--convergence tight` for Freq input. |
| **DFT frequency + thermochemistry** | `scripts/gaussian_freq.py` | Freq job parsed via cclib (ASE doesn't parse vib frequencies). Tighten the optimization first. |
| Vibrations / Hessian / ZPE (xTB-level) | `ase.vibrations.Vibrations` inline | Optimize to fmax ≤ 0.01 first, or you get spurious imaginary modes |
| HOMO-LUMO / dipole / charges | `scripts/single_point.py` (with `--calculator xtb`) | Returns gap, dipole, Mulliken charges, bond orders. **HOMO-LUMO is the raw eigenvalue gap — see `references/xtb.md` for the convention.** For DFT-level HOMO/LUMO, use `gaussian_sp.py` with cclib. |
| Binding / interaction / adsorption energy | three runs of `scripts/single_point.py` (or `gaussian_sp.py` for DFT) | E(complex) − E(A) − E(B); use the same calculator for all three |
| Transition state / barrier | NEB inline (see `references/ase_core.md`) | No turnkey script in v1 |
| Build a structure | `ase.build` inline | molecule / bulk / fcc111 / add_adsorbate |
| Analyze a trajectory | `scripts/analyze_traj.py` | RMSD / RMSF / energy drift / optional RDF |

### Step 2 — pick the calculator

Apply the first rule that fits the system, in this order:

1. **If the user explicitly named a calculator** (xTB, EMT, GFN2, TIP3P,
   …), use that one. *Why:* don't second-guess an explicit choice.
2. **If the system contains only EMT-supported metals** (Al, Cu, Ag, Au,
   Ni, Pd, Pt, plus H/C/N/O as adsorbates), prefer **EMT**. *Why:* it's
   free, instant, and the user probably wants a quick metallic-system
   answer.
3. **If the system is pure water** (H₂O molecules only), the choice
   depends on the task:
   - **Production MD** → **TIP3P**. *Why:* parameterized for exactly this
     case. **Requires `ase.constraints.FixBondLengths`** to keep the rigid
     O–H / H–H geometry — TIP3P is a rigid-body model and bare ASE will
     let the bonds vibrate, blowing up the simulation. See
     `references/ase_core.md` §Water (TIP3P + FixBondLengths). The
     bundled scripts do **not** auto-attach this constraint; you must add
     it inline before handing the script the structure, or write a short
     inline driver that does.
   - **One-off relaxations or quick energy / single-point checks** on
     small water systems → **GFN2-xTB**. *Why:* simpler — no constraints
     to set up — and small water clusters are well within xTB's accuracy
     range. `scripts/optimize.py` and `scripts/single_point.py` work as
     expected with `--calculator xtb`.
4. **If the system has organic / main-group chemistry** (heteroatoms,
   non-EMT elements, organic functional groups, ionic bonding), use
   **tblite GFN2-xTB**. *Why:* EMT will silently give nonsense for
   non-metals; GFN2-xTB is the cheapest method that knows real chemistry.
   *Sub-rule: if the user wants production-length explicit-solvent MD
   (≥ 100 ps in a TIP3P/OPC box) on a single small organic, switch to
   **GAFF2 + AM1-BCC** via `scripts/parameterize_gaff2.py` →
   `scripts/run_amber.py`. xTB MD with explicit solvent past ~100 ps
   is impractical (the box pushes well past 1k atoms once water is
   added); GAFF2 is the right tool for that task and the v1.3 scripts
   handle the antechamber → tleap → pmemd pipeline. See
   `references/amber.md` for force-field and water-model details.*

   > **⚠️ Architecture note (v1.3 Amber).** Amber is the **only engine in
   > the skill that does not run through ASE**. `parameterize_gaff2.py`
   > and `run_amber.py` shell out to AmberTools and pmemd directly; the
   > MD integration loop runs natively in pmemd, not in ASE. ASE handles
   > structure I/O at the boundaries and post-hoc analysis via
   > `analyze_traj.py`, but the simulation itself is opaque to ASE.
   > **The carve-out was a performance choice, not forced.** ASE does
   > expose an in-process Amber path via `ase.calculators.amber.SANDER`
   > (pysander Python bindings to sander), which would let
   > `run_md.py --calculator amber-sander` work cleanly. v1.3 chose
   > pmemd shell-out anyway because pmemd.cuda is GPU-accelerated and
   > ~10–50× faster than CPU sander on production-sized systems
   > (5–50k atoms); the SANDER path is CPU-only (pysander does not
   > bind to pmemd.cuda) and carries a "tested only for amber16"
   > disclaimer. **This trade is under review** — four options on the
   > table: keep pmemd shell-out, switch to SANDER+ASE Langevin,
   > remove Amber entirely, or build the missing API path (write a
   > proper ASE Calculator around pmemd/pmemd.cuda so the wrapper is
   > ASE-shaped and still hits pmemd.cuda speed). See
   > `references/amber.md` §1 and `PLAN.md` §"Phase 3" for the open
   > question. When recommending GAFF2 to the user, surface the
   > carve-out honestly so they can decide whether they want it.
5. **If the system is a transition-metal complex and GFN2 fails to
   converge**, fall back to **GFN1-xTB**. *Why:* GFN1 is more robust on
   d-block elements at the cost of some accuracy.
6. **If the system is past the xTB size cliff (~1k atoms or ~10 ps of
   xTB MD), reach for a MACE foundation model.** *Why:* GFN2-xTB MD
   stops being practical at ~1k atoms; MACE foundation models (MACE-OFF
   for organics, MACE-MP-0 for crystals/materials) deliver roughly
   DFT-quality energies and forces in that 1k–~2k atom range on a
   40 GB GPU. Use `--calculator mace` in `optimize.py` /
   `run_md.py`; routing is automatic by element set.
   **Cross-validation against GFN2-xTB is on by default for MD** —
   every 1 ps the script recomputes E and F on the latest frame
   through xTB and aborts the run when MAE_F > 100 meV/Å. This is
   the contract under which MACE is recommended at all; do not turn
   it off (`--no-validate`) without a specific reason. Read
   `references/ml_potentials.md` for the full method-selection rules
   and known failure modes (liquid mixtures, OOD geometries).
7. **If the system is past the MACE ceiling too** (>2k atoms on a
   40 GB GPU, >~1k on CPU, or anything past ~50k atoms in v1), say
   so out loud: "v1.2 caps at MACE-medium on a single GPU; v2.2 is
   slated to add larger ML potentials (CHGNet, Orb) and v2.3 adds
   Amber for biomolecular MD beyond GAFF2 small molecules." See
   `references/ase_core.md` §Appendix for the full size table.
8. **If the user explicitly wants DFT** (B3LYP, ωB97X-D, M06-2X,
   PBE0, post-HF, "publication thermochem", "transition-metal
   barriers within 1 kcal/mol", or "compute G298") and Gaussian is
   available — use **`gaussian_sp.py` / `gaussian_opt.py` /
   `gaussian_freq.py`**. *Why:* xTB tops out at ~few-kcal/mol error
   on relative energies and is unreliable on transition metals;
   DFT is the right tool. **No method/basis defaults** — surface a
   recommendation (ωB97X-D/def2-TZVP for organics; PBE0-D3(BJ)/def2-
   TZVP for transition metals; see `references/gaussian.md` §1) and
   confirm before running. The scripts also require explicit
   `--charge`, `--mult`, `--mem`, `--nproc`. Solvent → SMD by
   default. Freq workflow needs cclib (`pip install cclib`).

### Step 3 — confirm the calculator is installed

Read the `[OK]` / `[MISSING]` lines from `scripts/check_env.py`. If your
chosen calculator is `[MISSING]`, ask the user to install it; **do not
silently substitute a wrong-physics fallback**. EMT on an organic is the
classic failure mode — it will return numbers that look fine and are
meaningless.

## Verification & clarification

Two failure modes hurt this skill the most: (a) silently picking the wrong
physics or wrong parameters, and (b) re-asking the user something that the
prompt or the structure file already answers. Counter both with the rules
below.

### Clarify yourself first — only ask when you actually can't tell

Before asking the user anything, exhaust what is already determined:

- **Read the structure file.** Element list, atom count, periodicity,
  whether it's a slab, charge/multiplicity if present — `ase.io.read` and
  inspect. Don't ask "is this a metal?" if the file says `Pt`.
- **Re-read the prompt for already-named specs.** "MD at 300 K for 10 ps"
  has named the temperature, the duration, and (implicitly, by "at") an
  NVT ensemble. Don't re-ask any of them.
- **Run `check_env.py`** so you know which calculators are available before
  recommending one.
- **Apply the method-selection tree above** to derive a defensible default
  from system + task. If the rules give a unique answer, that's your
  answer — don't ask the user to choose.

When the answer is still genuinely underdetermined after all of that, *then*
ask. Frame the question with the option you'd pick and the reason — e.g.,
"GFN2-xTB looks right here because the system has heteroatoms; want me to
fall back to GFN1 for d-block robustness instead?" — beats a blank "which
method?".

### Ask the user to verify before recommending execution

After choosing parameters, restate them in a short block and ask the user to
confirm before suggesting they run anything. The minimum to surface:

- Calculator (and GFN level if applicable)
- Optimizer / ensemble
- For MD: temperature, friction, timestep, n_steps
- For optimization: fmax, max_steps
- Output paths that will be written

Keep it tight — a 4–6 line summary, not a paragraph. If the user has
already explicitly approved the plan in this conversation, don't re-ask.
The point is to catch wrong-physics and wrong-parameter mistakes (EMT on
an organic, 2 fs timestep with unconstrained H) before they cost the user
wall-clock time, not to gate every interaction.

## Scripts — when to invoke each

All scripts live in `scripts/` and are parameterized via argparse.
Run with `--help` to see options.

**Default — call the script.** When a bundled script's purpose matches
the user's task, invoke the script with its CLI flags. Don't rewrite its
logic inline. Bundled scripts have sane defaults, tested code paths,
consistent CLI/output formats, and stay maintained as the skill evolves;
inline code reinvents all of that and is harder for the user to re-run
later with different parameters.

**Carve-out — write inline.** Only when the task needs logic the scripts
don't expose: a custom analysis function the user explicitly asked for,
a non-standard ensemble (NPT, constrained dynamics), or a one-shot
`ase.build` call that doesn't have a corresponding script. If the gap
is narrow — a missing flag or an unexposed parameter — prefer **adding
the flag to the script** and using it over a one-off inline rewrite.

**When inline is allowed — and what doesn't count.** Going inline
requires a *specific, named* capability that the bundled script lacks
(e.g., "run_md.py has no `--barostat` flag, and the user asked for
NPT"). A reader should be able to confirm the gap by running the
script's `--help`. The following are **not** justifications:

- *User phrasing.* "Write the script", "give me a script", "show me
  the code" — the bundled CLI invocation **is** a script. Treat
  these phrases as satisfied by the one-liner.
- *Readability or pedagogy.* If you want to show the user what's
  happening, point at `scripts/<name>.py` and describe it; don't
  retype it.
- *Tweaks already covered by flags.* A different fmax, timestep,
  ensemble, calculator, or seed is what the flags exist for.

If you go inline, name the gap in one sentence before the code. No
sentence → no carve-out → use the bundled CLI.

Per-script use:

- **`scripts/check_env.py`** — Reports installed backends and a one-line
  capability summary. **Use for:** the first thing you do on any
  non-trivial task, so you recommend a method the environment actually
  supports.
- **`scripts/optimize.py`** — Geometry optimization with BFGS / FIRE /
  LBFGS, calculator EMT / LJ / TIP3P / xTB / MACE. Real-gas LJ via
  `--epsilon`/`--sigma`/`--rc`. MACE via `--calculator mace`
  (auto-routed to MACE-OFF for pure organics, MACE-MP-0 otherwise).
  **Use for:** any "minimize / relax / optimize / find the equilibrium
  geometry" task on a single structure.
- **`scripts/run_md.py`** — NVE / NVT-Langevin / NVT-Nose-Hoover MD with
  EMT / LJ / TIP3P / xTB / MACE. Sensible defaults for organic molecules
  (1 fs, 300 K, Langevin friction 0.01/fs, log every 100 steps). Real-gas
  LJ via `--epsilon`/`--sigma`/`--rc`. With `--calculator mace`,
  cross-validation against GFN2-xTB runs automatically every 1 ps
  (`--validate-every`); MD aborts if MAE_F > 100 meV/Å
  (`--abort-mae-f`). Disable with `--no-validate` only for specific
  reasons. **Use for:** any "run dynamics / thermalize / equilibrate /
  produce a trajectory" task with standard ensembles.
- **`scripts/ml_calculator.py`** — Helper module exposing
  `make_ml_calc(atoms, system_class=, device=, model_size=)`. Imported
  by `optimize.py` and `run_md.py` when `--calculator mace`. **Use
  for:** the rare inline case that needs a MACE calculator outside
  the bundled scripts. Run as `python scripts/ml_calculator.py
  --structure mol.xyz` to print routing without loading weights.
- **`scripts/validate_ml_md.py`** — Post-hoc cross-validation of a
  saved MACE trajectory against GFN2-xTB. Same MAE_F threshold as
  `run_md.py` runtime validation; writes `validation.csv`. **Use
  for:** trajectories produced with `--no-validate`, or to re-validate
  with a different reference / stride.
- **`scripts/parameterize_gaff2.py`** — Drives `antechamber -c bcc`
  (AM1-BCC charges) → `parmchk2` (frcmod) → `tleap` (solvate in
  TIP3P or OPC, neutralize with Na+/Cl-) for a small organic
  molecule. Output is the `.prmtop` / `.rst7` pair consumed by
  `run_amber.py`. **Use for:** any "parameterize this ligand /
  small molecule for explicit-solvent MD" task. **Mandatory:
  `--net-charge` matches the formal charge** — getting it wrong
  silently shifts every partial charge.
- **`scripts/run_amber.py`** — Runs Amber MD on a `.prmtop` / `.rst7`
  pair. `--protocol standard` runs min → heat (50 ps NVT, 0→300 K)
  → density (100 ps NPT) → prod (default 500 ps NPT). Engine
  selection auto-picks `pmemd.cuda` > `pmemd` > `sander`; override
  with `--engine`. Outputs NetCDF `.nc` ready for
  `analyze_traj.py`. **Use for:** any GAFF2 small-molecule MD task,
  or BYO-prmtop runs where the topology was generated outside the
  skill. **Note:** v1.3's `mdin` defaults are tuned for GAFF2
  small molecules; protein/NA prmtop files will run but may want
  different cutoffs / restraints. **Architectural carve-out:** the
  MD loop runs in pmemd, not ASE. The script prints this on every
  invocation; see the architecture note above for the rationale and
  the open question on whether to keep this engine in the skill at all.
- **`scripts/gaussian_sp.py`** — DFT single-point E/F/dipole via
  `ase.calculators.gaussian.Gaussian`; auto-falls back to g09 if g16
  isn't on PATH. Optional cclib parse for Mulliken/Löwdin/Hirshfeld
  charges and HOMO/LUMO eigenvalues. **All of `--method`, `--basis`,
  `--charge`, `--multiplicity`, `--mem`, `--nproc` are required —
  no silent defaults**, surface a recommendation and confirm. SMD
  is the documented water-solvent default. **Use for:** any DFT
  single-point request — energy, forces, dipole, MO eigenvalues,
  partial charges at DFT level.
- **`scripts/gaussian_opt.py`** — DFT geometry optimization via
  `GaussianOptimizer` (delegates to Gaussian's L103 internal
  optimizer in one g16/g09 invocation). `--convergence` is a string
  (`loose`/`default`/`tight`/`verytight`), not a numeric eV/Å —
  Gaussian's convention. Use `tight` or `verytight` if the
  optimized geometry feeds into a Freq job. **Use for:** any
  DFT-level optimization, especially as Freq input.
- **`scripts/gaussian_freq.py`** — DFT frequency + thermochemistry
  (vib_freqs / ZPE / enthalpy / Gibbs G), parsed via **cclib**
  (mandatory dep — ASE's read_gaussian_out doesn't parse vib
  frequencies). Reports imaginary modes as a warning. **Use for:**
  thermochem on a tightly-optimized geometry. The freq method/basis
  must match the optimization method/basis; the script doesn't
  enforce this — surface it to the user.
- **`scripts/single_point.py`** — Single-point energy plus xTB electronic
  observables (dipole, Mulliken charges, Wiberg bond orders, HOMO-LUMO
  raw eigenvalue gap). Tagged `key=value` output. Optimize first —
  single-point observables on a strained geometry are nonsense. **Use
  for:** any energy / force / electronic-observable request on a fixed
  geometry, including binding-energy decomposition (run three times).
- **`scripts/analyze_traj.py`** — RMSD, RMSF, energy drift, optional RDF
  from a trajectory. Saves PNG plots and CSV data alongside the input.
  **Use for:** any "analyze this trajectory / RMSD vs. frame 0 / check
  energy drift / compute RDF" task. **These analyses ARE the script's
  primary purpose, not a subset of it — do not write a substitute for
  any of them inline.** The script handles edge cases (Kabsch
  alignment, missing-calculator fallback for energy drift, periodic
  unwrapping for RDF) that an inline rewrite will get wrong.

### Growing the skill: when to offer to bundle new scripts

The default chain is: bundled script when one matches → inline code when
none does. Add a third option: when the inline code looks like recurring
work, **offer to promote it to a new bundled script**.

**Offer when ALL of these are true:**

- The inline code is substantial — > ~30 lines, **or** it implements a
  complete workflow with parameters worth exposing as CLI flags.
- No existing script in `scripts/` covers the task type. (If one does,
  point the user at it instead — don't make a duplicate.)
- The user's request reads as recurring work — phrasing like "for each
  molecule," "I'll run this on a bunch of systems," "every time I get a
  new structure," or any other parametric framing.

**Don't offer when:**

- The inline code is trivial (< ~30 lines, single-purpose, e.g., a
  small `ase.build` call).
- The task is already covered by an existing script — point the user
  there instead.
- The request is one-shot exploratory ("what's the energy of this
  molecule?") or conversational / definitional.

**What the offer looks like.** End the response with a paragraph along
these lines (adapt the specifics to the actual task):

> I wrote this inline because no existing script in `scripts/` covers
> [specific task]. If this is something you'll do repeatedly, I can
> refactor it into `scripts/<name>.py` with proper argparse, a
> docstring that explains when to reach for it, and a SKILL.md
> §Scripts entry — and the next time you (or anyone using this skill)
> hits the same task, the bundled script will be the default. Want me
> to do that?

**If the user says yes:**

1. Refactor the inline code into `scripts/<descriptive_name>.py`. Use a
   verb-based name following existing conventions (`optimize.py`,
   `run_md.py`, `analyze_traj.py`).
2. Add argparse with sensible defaults and useful `--help` text.
3. Add a top-of-file docstring that explains **when** to reach for the
   script — that's what helps future Claude sessions trigger it.
4. Match output conventions of existing scripts (banner line on start,
   tagged `[OK]` / `[INFO]` lines, plots/CSVs alongside the input,
   meaningful exit codes).
5. Add a one-line bullet to SKILL.md §Scripts in the same format as the
   existing entries (`**Use for:** ...`).
6. Run the new script with `--help` and one realistic example invocation
   to verify it works. Report success or failure to the user.

**If the user says no:** leave the inline code alone. Don't ask again
in the same conversation.

**Why this matters.** The skill grows by accretion of workflows that
turn out to be recurring. Static curation can't anticipate every useful
pattern. Asking the user is the cheapest, highest-signal way to find
which inline patterns deserve promotion: every "yes" is direct evidence
of a recurring need, every "no" is direct evidence the work was a
one-off. Over time, `scripts/` becomes a frequency-weighted snapshot of
what the skill is actually used for.

## References — read these on demand

Each reference file is short and topic-scoped. Read the file when its topic
comes up; do not preload them all.

- **`references/ase_core.md`** — Read for: structure I/O (read/write,
  formats), `ase.build` patterns, optimizer choice, MD integrators and
  their constructor signatures, units (eV / Å / fs / kB), the Trajectory
  format, NEB scaffolding.
- **`references/xtb.md`** — Read for: tblite install, GFN1 vs GFN2 choice,
  the standalone `xtb` binary (GFN0, GFN-FF), what observables xTB
  exposes (energy, forces, dipole, HOMO-LUMO, Mulliken), known
  limitations (transition metals, periodic systems).
- **`references/analysis.md`** — Read for: when to use ASE's built-in
  trajectory readers vs MDAnalysis, recipes for the analyses
  `analyze_traj.py` implements, common pitfalls (alignment, periodic
  unwrapping).
- **`references/ml_potentials.md`** — Read for: when to reach for MACE
  vs stay with xTB, the cross-validation contract (1 ps cadence,
  MAE_F > 100 meV/Å abort), known MACE failure modes (liquid mixtures,
  the ~1–2k atom GPU ceiling, OOD geometries), GPU/CPU notes,
  troubleshooting (OOM, weight downloads).
- **`references/amber.md`** — Read for: when GAFF2 wins over GFN2-xTB,
  the antechamber → parmchk2 → tleap → pmemd pipeline, force-field
  and water-model choices (GAFF2 vs GAFF, TIP3P vs OPC, AM1-BCC vs
  RESP), engine selection (pmemd.cuda vs pmemd vs sander), known
  failure modes (charge parity, antechamber aromatic perception, box
  sizing), troubleshooting. Protein/NA MD via ff19SB+OPC / OL21 is
  deferred to v2.3 — the `mdin` defaults in v1.3 are GAFF2-tuned.
- **`references/gaussian.md`** — Read for: when Gaussian beats xTB,
  the no-defaults policy + recommended method/basis choices
  (ωB97X-D/def2-TZVP for organics, PBE0-D3(BJ)/def2-TZVP for TM),
  SMD vs PCM solvation, g16 vs g09 differences, cclib coverage
  (vib_freqs, thermochem, MO eigenvalues, Mulliken/Löwdin/Hirshfeld
  charges; NPA out of scope), known failure modes (multiplicity
  errors, solvation mismatch across SP/Opt/Freq chain, GAUSS_SCRDIR
  issues), troubleshooting. Opt=TS / IRC / NBO / TDDFT / post-HF
  are explicitly deferred to v3+.

## Defaults and conventions

- **Units**: ASE uses eV, Å, ASE-time-units. Use `ase.units.fs` /
  `ase.units.kB` rather than raw numbers. Temperature kwarg is
  `temperature_K=` (canonical since ASE 3.21.0).
- **Timestep**: 1 fs is safe for organic molecules with all-atom dynamics.
  Bump to 2 fs only if you constrain hydrogen bonds (ASE doesn't do
  RATTLE/SHAKE elegantly, so 1 fs is the safer default).
- **Friction (Langevin)**: 0.01 / fs is a reasonable thermostat coupling
  for production. Higher values (0.1 / fs) for fast equilibration.
- **Optimization tolerance**: `fmax=0.05 eV/Å` for production geometries;
  `0.01 eV/Å` for vibrational analysis input.
- **Trajectory format**: prefer `.traj` (ASE binary, includes calculator
  results) over `.xyz` (positions only) when energies/forces matter
  downstream.
- **Random seed**: Set `seed` in MD integrators if reproducibility matters
  to the user.

## Reporting results

When you finish a task, report:
1. The method used (calculator + integrator/optimizer) and **why** it was
   chosen given system size, available backends, and accuracy needed.
2. Final numbers (energy, fmax, temperature, etc.) with units.
3. Where outputs were written (trajectory, plots, CSVs).
4. Any caveats (e.g., "GFN2-xTB; transition-metal accuracy is limited",
   "NVE energy drift was 0.3 meV/atom over 1 ps — reasonable").

## What v1 does NOT support

Tell the user honestly when their request crosses the line:
- Amber for protein / nucleic-acid MD — v1.3 ships GAFF2 small-molecule
  MD only. Protein (ff19SB+OPC) and nucleic-acid (OL21) MD are deferred
  to v2.3. Users with a `.prmtop` from their own workflow can still run
  `run_amber.py` against it; `mdin` defaults are GAFF2-tuned but most
  parameters are reasonable for biomolecules too — flag this honestly.
- Transition-state searches via Gaussian (`Opt=TS`, QST2/QST3) and
  IRC — v1.4 ships SP / Opt / Freq, but not TS. TS needs a good
  Hessian guess and IRC verification; push to v3+.
- Anharmonic frequencies, NBO/NPA charges, post-Hartree-Fock methods
  (CCSD/MP2/CASSCF), excited-state methods (TDDFT/CIS/EOM-CCSD) —
  out of scope for v1.4 Gaussian; see `references/gaussian.md` §7.
- VASP, Quantum ESPRESSO — no v2 plan; community CP2K / FHI-aims
  bridges may land in v3.
- Other ML potentials — CHGNet (charge-aware materials), Orb-v3
  (confidence-head OOD signal), M3GNet, SevenNet — planned for v2.2+.
  v1.2 ships MACE only; if a user asks for the others, say "v2.2 is
  slated to add CHGNet for charge-aware materials; today MACE-MP-0
  covers most of the same systems with the cross-validation contract
  documented in `references/ml_potentials.md`."
- Free energy methods (TI / FEP / MBAR), enhanced sampling (REMD,
  metadynamics, umbrella sampling), QM/MM, constant-pH MD.
- RESP charges via Gaussian — v1.3 uses AM1-BCC for GAFF2 only.
- SLURM/HPC submission scripts. Gaussian users wrap `gaussian_*.py`
  in their own queue script.
- Web GUI / visualization servers.
