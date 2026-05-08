# Extension Map — Big Amber Features Not Yet Shipped

This is the "we know where this goes" map. v1.0 deliberately ships
a focused MD-first core; the rest of Amber's ecosystem is named
here so honest deferrals point at concrete future locations rather
than waving vaguely at "more work."

This is **not** a roadmap commitment. Items move into v1.x when
usage data or an explicit user request justifies the engineering
work.

## Map

| Feature | Lands in | Architectural change | Est. work |
|---|---|---|---|
| **Accelerated MD (aMD)** | `amber_md.py --boost amd` (new flag) | mdin block: `iamd, ethreshd, alphad, ethreshp, alphap` | small (~1 day) |
| **Steered MD (SMD/jar)** | `amber_md.py --boost smd --jar-file <DISANG>` | mdin block: `jar=1, nmropt=1` + DISANG file passthrough | small |
| **NMR-style restraints (DISANG)** | `amber_md.py --disang <file>` | mdin `nmropt=1` + DISANG passthrough | small |
| **Umbrella sampling** | `amber_md.py --boost umbrella --restraint-file <DISANG>` | mdin `nmropt=1` + DISANG; post-processing via WHAM (`amber_wham.py` add-on) | medium |
| **WHAM / MBAR free energy from US/REMD** | `amber_mbar.py` (new add-on) | pymbar dependency; reads per-replica or per-window energies | medium |
| **Hamiltonian REMD** | `amber_remd.py --type H` (already pre-wired) | per-replica prmtop variation (lambda scaling); reuses groupfile + MPI engine pick | medium |
| **REST2 (replica-exchange with solute scaling)** | `amber_remd.py --type REST2` | similar to H-REMD but with solute scaling instead of lambda | medium |
| **Free energy: TI / FEP** | `amber_fep.py` (new) | TI mdin templates with `clambda, mbar_lambda`; pmemd.cuda TI engine; multi-window orchestration | large |
| **Constant-pH MD** | `amber_cpH.py` (new) | mdin: `icnstph=1, ntcnstph, solvph`; cpinutil pre-step | medium |
| **Constant-redox MD** | `amber_cpE.py` (new) | mdin: `icnste=1`; cpein-style prep | medium |
| **QM/MM** | `amber_qmmm.py` (new) | mdin `&qmmm` block; QM-engine selection (sqm, GAUSSIAN, ORCA) needs a sub-design | large |
| **Membrane / lipid (LIPID17)** | `amber_prep.py --membrane` + `amber_md.py --barostat anisotropic` | tleap LIPID17 leaprc; `ntp=2/3, csurften` mdin block | medium |
| **Multi-GPU pmemd.cuda** | `_amber.pick_engine(--gpu-count)` | engine pick parameterized; `pmemd.cuda.MPI` with `CUDA_VISIBLE_DEVICES`; usually a perf-only win | small |
| **PLUMED bridge (metadynamics, COLVARS)** | `amber_md.py --plumed <plumed.dat>` | engine variant `pmemd.MPI.plumed`; runtime PLUMED check | medium |
| **SHAKE-free (longer integration step) workflows** | `amber_md.py --no-shake` | document `ntc=1, ntf=1, dt=0.001` recipe | docs only |
| **Trajectory mutation / topology editing** | `amber_parmed.py` (new add-on wrapping ParmEd) | calls `parmed -i <deck>`; uses `_amber.py` helpers | small-medium |
| **Conformational clustering** | `amber_analyze.py --cluster` (extend existing) | cpptraj `cluster` block; outputs cluster representative pdbs | small |
| **Secondary structure (DSSP)** | `amber_analyze.py --dssp` (extend existing) | cpptraj `secstruct` block | small |
| **REMD lambda windows / replica swap statistics** | `amber_analyze.py --remd-stats` (extend existing) | already partially shipped via `rem.log` parser; expose | small |
| **HPC submission templates (SLURM / PBS / LSF)** | `amber_submit.py` (new) | renders queue scripts wrapping `amber_run.py`; v2 candidate | small |
| **Per-residue free-energy decomposition (gas-phase)** | already supported via `amber_score.py --per-residue` | n/a | shipped |

## When to consult this map

When a user asks for a feature this skill does not ship:

1. Look up the row above.
2. Cite the planned location ("aMD lands as `amber_md.py --boost amd`")
   so the deferral is concrete.
3. If the user has a workaround (e.g., they want SMD but can write
   their own DISANG file), point them at `amber_md.py --stage custom
   --mdin <their-mdin>` so they aren't blocked.
4. Never silently fabricate a workflow — say "this skill doesn't
   ship X yet; the planned location is Y."

## Reading conventions

- "small" = ~1 day of work; mostly mdin-flag additions.
- "medium" = ~3-5 days; new file format, new parser, or new orchestration.
- "large" = ~weeks; new sub-design needed (e.g., QM-engine selection for QM/MM).

## Items NOT on this map

These are out of Amber's lane entirely; the user should be pointed
at a different tool:

- **VASP, Quantum ESPRESSO, CP2K, FHI-aims** — solid-state DFT codes; not Amber. See `ase-chemist` for ASE bridges (deferred there too).
- **GROMACS, NAMD, OpenMM** — different MD engines. We don't bridge to them.
- **Schrödinger, MOE, Maestro** — commercial workflow tools.
- **AlphaFold, RoseTTAFold** — structure prediction, not MD.

## Why these are deferred, not implemented

Each row is engineering work, not a missing line of code. Three
reasons we defer:

1. **Validation cost.** Shipping a feature without a real end-to-end
   test creates a "we wrote the code but never finished a job"
   liability. v1.0 ships features the team can run. New features
   need the same standard.
2. **Scope creep.** Amber spans ~30 years of MD research. A skill
   that tries to ship all of it becomes a thin wrapper that has no
   opinion on anything. Better to ship a focused MD core well.
3. **Routing surface.** Every shipped feature grows SKILL.md's
   description and increases the chance of trigger collisions with
   `ase-chemist` or other future skills. Defer until usage data
   shows demand.

When usage data does justify a row, the architectural change is
named — there are no architectural unknowns. Implementation is then
mostly mechanical.
