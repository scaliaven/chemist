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
| `shutil.which("sander")` | reference MD engine, ships with AmberTools (free) |
| `shutil.which("pmemd")` | production MD engine, license-restricted |
| `shutil.which("tleap")` | system-prep tool — needed for end-to-end workflows |
| `os.environ.get("AMBERHOME")` | install root; used to disambiguate multiple installs |

Reporting rule: the backend is "available" if **either** `sander` or
`pmemd` resolves on `PATH`. Report whichever resolved and the resolved
path (so users with multi-install boxes can see which one will be
picked). `tleap` is a separate concern — note it as missing if absent
even when `sander` is present, because v2 system-prep workflows need
it.

Do **not** check whether the license server is reachable. Amber is
mostly free now (AmberTools) but pmemd.cuda still needs a license at
some sites; license-server probing is fragile and out of scope for the
env check.

## §3. Scope when implemented (v2)

When v2 work begins on Amber, the chapter that replaces this stub will
cover:

- Protein and nucleic-acid MD with **ff14SB / ff19SB / OL15** (ff14SB
  default for proteins, OL15 default for nucleic acids).
- **GAFF / GAFF2** for small organic molecules where a force field beats
  GFN2-xTB on cost.
- Basic system preparation via `tleap`: solvation in a TIP3P box,
  neutralizing counter-ions, simple disulfide handling.
- Short equilibration runs via `sander` (minimization → heating →
  density equilibration → short NVT).
- Production MD via `pmemd` (or `pmemd.cuda` when a GPU is detected),
  driven from an ASE-style script that writes Amber input decks and
  parses the `.nc` trajectory back.
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
4. **ASE-Amber bridge vs shell-out.** `ase.calculators.amber` exists
   but is thin and underused. Is it worth investing in (in-process
   MD via Amber-as-calculator), or should v2 just write input decks
   and parse output files?
5. **Default equilibration protocol.** Skill-bundled defaults
   (min → heat → density → short prod) or always user-driven? Bundling
   is more useful but locks in opinions; user-driven is more flexible
   but reads as "the skill doesn't actually help."
