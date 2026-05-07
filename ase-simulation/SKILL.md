---
name: ase-simulation
description: Use this skill whenever the user wants to run, set up, or analyze atomistic simulations on molecules or materials. This covers: molecular dynamics (MD, NVE, NVT, NPT, Langevin, Nose-Hoover) including thermalization, equilibration, and "warm up the system" requests; geometry optimization, energy minimization, or relaxation (BFGS, FIRE, LBFGS — "minimize this molecule", "relax this structure", "find the equilibrium geometry"); vibrational frequency, normal-mode, Hessian, and zero-point-energy analysis; NEB and transition-state searches; structure building (small molecules, bulk crystals, surfaces like fcc111, slabs with adsorbates); trajectory analysis (RMSD, RMSF, RDF, energy drift); single-point energy and force evaluation; binding, interaction, and adsorption energy calculations; and electronic observables like HOMO-LUMO gap, dipole moment, or Mulliken charges. Use this skill for any request involving force fields, semi-empirical methods (xTB / GFN1 / GFN2), DFT-style reasoning about which method to pick, or any computational chemistry / materials task that mentions ASE, EMT, Lennard-Jones, TIP3P, tblite, or xtb. Reach for this skill even when the user does not name ASE — phrases like "minimize this molecule", "relax this geometry", "thermalize at 300 K", "equilibrate the system", "compute the binding energy", "run MD on water", "build a Pt(111) slab", and "compute frequencies" should all trigger this skill.
license: MIT
---

# ASE Simulation Skill (v1.1)

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

`tblite` ships GFN1-xTB and GFN2-xTB and is the supported successor to the
deprecated `xtb-python`. If `check_env.py` reports `[BROKEN] tblite ...
C extension unloadable`, the pip wheel is libgfortran-incompatible — switch
to `conda install -c conda-forge tblite-python`. The standalone `xtb`
binary (Grimme group) adds GFN0 and GFN-FF if it's on PATH.

## Method selection

Walk these three steps in order. Each rule names *what* to do and *why*; if
the user's case doesn't fit the "because", the rule probably doesn't apply
and you should keep walking.

### Step 1 — what task is this?

| Task | Tool | Notes |
|---|---|---|
| Optimize / minimize / relax | `scripts/optimize.py` | FIRE for far-from-equilibrium, BFGS otherwise |
| MD at temperature T | `scripts/run_md.py` | Langevin NVT is the default ensemble |
| Vibrations / Hessian / ZPE | `ase.vibrations.Vibrations` inline | Optimize to fmax ≤ 0.01 first, or you get spurious imaginary modes |
| HOMO-LUMO / dipole / charges | `scripts/single_point.py` (with `--calculator xtb`) | Returns gap, dipole, Mulliken charges, bond orders. **HOMO-LUMO is the raw eigenvalue gap — see `references/xtb.md` for the convention.** |
| Binding / interaction / adsorption energy | three runs of `scripts/single_point.py` | E(complex) − E(A) − E(B); use the same calculator for all three |
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
5. **If the system is a transition-metal complex and GFN2 fails to
   converge**, fall back to **GFN1-xTB**. *Why:* GFN1 is more robust on
   d-block elements at the cost of some accuracy.
6. **If the system is large enough that the chosen method becomes
   impractical** (rough cliffs: xTB MD past ~1k atoms, anything past
   ~50k), say so out loud: "v1 can't deliver that — GFN2-xTB MD becomes
   impractical past 1k atoms, and v1 has no classical force field for
   organics. v2 will add Amber and ML potentials; for now we can do a
   single-point or a short geometry optimization, but not production
   MD." See `references/ase_core.md` §Appendix for the full size table.

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
  LBFGS, calculator EMT / LJ / TIP3P / xTB. Real-gas LJ via
  `--epsilon`/`--sigma`/`--rc`. **Use for:** any "minimize / relax /
  optimize / find the equilibrium geometry" task on a single structure.
- **`scripts/run_md.py`** — NVE / NVT-Langevin / NVT-Nose-Hoover MD with
  EMT / LJ / TIP3P / xTB. Sensible defaults for organic molecules
  (1 fs, 300 K, Langevin friction 0.01/fs, log every 100 steps). Real-gas
  LJ via `--epsilon`/`--sigma`/`--rc`. **Use for:** any "run dynamics /
  thermalize / equilibrate / produce a trajectory" task with standard
  ensembles.
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

The following reference files are **stubs for v2** — they document
intended scope and detection logic but are **not implementations**.
Do not follow them as workflows. If a user asks about one of these
backends, point at the stub for an honest description of the limit
and pick a v1-supported alternative.

- `references/amber.md`         (stub — planned for v2, not implemented)
- `references/gaussian.md`      (stub — planned for v2, not implemented)
- `references/ml_potentials.md` (stub — planned for v2, not implemented)

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
- Amber, Gaussian, VASP, Quantum ESPRESSO (planned for v2)
- ML potentials — MACE, CHGNet, ORB, etc. (planned for v2). If a user
  asks for one, say: "v2 will support those; for now GFN2-xTB is in
  the same accuracy ballpark for organics at ~10× the cost."
- Free energy methods, enhanced sampling, metadynamics
- Implicit/explicit solvation models beyond TIP3P water clusters
- SLURM/HPC submission scripts
- Web GUI / visualization servers
