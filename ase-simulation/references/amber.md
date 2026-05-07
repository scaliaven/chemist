# Amber Reference (STUB — planned for v2, not implemented)

> **This backend is not yet supported by the ase-simulation skill.** Do
> not generate Amber input files or shell out to `sander` / `pmemd` from
> within a skill response. This file exists to (a) document how the
> environment detects an Amber install, (b) record the intended v2 scope
> so contributors know what they are signing up for when they pick this
> up, and (c) capture the open questions that two weeks of real-usage
> data are expected to answer.

## §1. Status

Amber is planned for **v2** of the ase-simulation skill. It is not
currently supported. If the user has a task that needs Amber, do this
today:

- For organic / main-group systems up to ~1000 atoms, recommend
  **GFN2-xTB** via the existing `optimize.py` / `run_md.py` /
  `single_point.py` scripts. Be explicit about the size cliff: xTB MD
  past ~1k atoms is impractical and Amber is the right tool, just not
  yet wired in.
- For protein / nucleic-acid systems, or any system where the user
  already has a `.prmtop` / `.inpcrd` topology pair, tell the user
  honestly that the skill cannot drive Amber yet. They should run
  `sander` or `pmemd` themselves outside the skill; the skill can help
  with **trajectory analysis** afterwards via `analyze_traj.py` and
  MDAnalysis (`.nc` / `.dcd` reading is supported).
- Do **not** stitch together a hand-rolled `tleap` script and shell out
  from a skill response. That code path is not tested, not maintained,
  and silently producing a broken topology is exactly the failure mode
  v2 needs to prevent.

## §2. Detection

`scripts/check_env.py` should report Amber as available iff at least
one production engine is on `PATH`:

| Check | Purpose |
|---|---|
| `shutil.which("sander")` | reference MD engine, ships with AmberTools |
| `shutil.which("pmemd")` | production CPU MD engine, ships with AmberTools25 |
| `shutil.which("pmemd.cuda")` | production GPU MD engine, ships with AmberTools25 |
| `shutil.which("tleap")` | system-prep tool — needed for end-to-end workflows |
| `shutil.which("antechamber")` | small-molecule parameterization — needed for GAFF2 |
| `os.environ.get("AMBERHOME")` | install root; used to disambiguate multiple installs |

Reporting rule: the backend is "available" if **either** `sander` or
`pmemd` resolves on `PATH`. Report whichever resolved and the resolved
path (so users with multi-install boxes can see which one will be
picked). `tleap` and `antechamber` are separate concerns — note each
as missing if absent even when an MD engine is present, because v2
system-prep workflows need them.

As of AmberTools25, the entire Amber suite — including `pmemd.cuda` —
is open-source and license-free. There is no license server to probe;
remove any "license-restricted" reasoning from older docs.

A constraint that does need to be documented at detection time:
**`ase.calculators.amber.Amber` is single-point only.** It re-launches
`sander` once per `calculate()` call, which is fine for a frozen
single-point but catastrophic for MD (the per-step subprocess overhead
dwarfs the actual integration cost). It also **rejects non-orthogonal
cells** in `write_coordinates()`, which kills truncated-octahedron
solvation through the calculator path. v2 therefore uses **shell-out
to `pmemd` / `sander` directly**, not the ASE Amber calculator, for
the integration loop. ASE's role is structure I/O at the boundaries.

## §3. Scope when implemented (v2)

When v2 work begins on Amber, the chapter that replaces this stub will
cover:

- Protein MD with **ff19SB + OPC** (the post-2020 community default;
  ff14SB is one generation behind and stays as a legacy fallback for
  users with existing TIP3P-built systems).
- Nucleic-acid MD with **OL21** (the OL15 → OL21 update is now standard).
- **GAFF2** for small organic molecules — default — with **AM1-BCC**
  charges from `antechamber`. Plain `GAFF` stays as a legacy option
  for users coming from older Amber tutorials.
- Basic system preparation via `tleap`: solvation in a TIP3P or OPC
  box, neutralizing counter-ions, simple disulfide handling.
- Short equilibration runs (minimization → heating → density
  equilibration → short NVT) using `sander` for minimization and
  `pmemd` / `pmemd.cuda` for the dynamics stages — `sander` is too slow
  for production MD past minimization.
- Production MD via `pmemd.cuda` when a GPU is detected, else `pmemd`,
  driven from a Python orchestrator that writes Amber input decks
  (`mdin`) and parses the `.nc` trajectory back. **Not** driven through
  `ase.calculators.amber.Amber` (see §2 for why).
- Trajectory analysis via the existing `analyze_traj.py` plus MDAnalysis
  (no new analysis code; `.nc` reading already works).

It will explicitly **not** cover, in v2:

- Free-energy methods (TI / FEP / MBAR).
- Enhanced sampling (REMD, accelerated MD, metadynamics).
- QM/MM with sander/quick or external QM engines.
- Umbrella sampling and other constrained-coordinate schemes.
- Constant-pH MD or any titration protocol.

Those are v3+ candidates — research workflows that need their own
design pass and their own validation suite.

## §4. Open questions (to be answered by usage data)

These are the questions whose answers should drive the v2 design. The
first thing to do when picking up v2-Amber is to read the notes log and
answer them.

1. **Protein MD vs small-molecule GAFF — which is the dominant ask?**
   They have very different prep pipelines. Protein-first means tleap +
   ff14SB are the priority; small-molecule-first means antechamber +
   GAFF parameterization is the priority.
2. **System-prep ownership.** Do users want the skill to drive `tleap`
   end-to-end (PDB → solvated box → topology), or do they bring their
   own `.prmtop` / `.inpcrd` and just want the skill to run MD on it?
   The first option is much more code; the second is much less risky.
3. **SLURM / queue submission.** Does the skill need to bundle its own
   submission templates, or do users have group-specific templates that
   should be respected? (v1 has no submission story at all, so this
   question lands fresh.)
4. **ASE-Amber bridge vs shell-out.** *Answered (2026-05-07): shell-out.*
   Reading the ASE source confirmed `ase.calculators.amber.Amber` is
   single-point only and rejects non-orthogonal cells; both make it
   unusable as an MD integrator. v2 writes input decks and parses
   output files; ASE handles structure I/O at the boundaries.
5. **Default equilibration protocol.** *Answered (2026-05-07): bundle
   min → heat → density → prod as `--protocol standard`, expose
   individual stages as flags.* This matches what AmberMDrun, the
   BioExcel tutorials, and the AMBER manual all document; refusing
   to bundle reads as the skill not actually helping.
