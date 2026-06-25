# amber-chemist (v1.0)

Amber-native molecular dynamics skill for Claude Code. Sibling to
`ase-chemist`. Focused on **MD-first** workflows: single-replica MD
plus Temperature Replica-Exchange (T-REMD), with cpptraj-driven
analysis and MMPBSA endpoint scoring as add-ons.

## What v1.0 ships

**Primary core — normal (single-replica) MD**

- `amber_md.py --stage {min, heat, density, prod, custom}`: each stage is independently runnable. `custom` takes a verbatim `--mdin` so power users keep escape-hatch control.
- `--restart` chains stages (heat → density → prod). `--extend` chains chunks of the same stage (auto-numbered `prod_2.{nc,rst7,mdout}`, `_3`, …).
- Restraints: `--restraint-mask` + `--restraint-weight` for positional restraints during heating / density (and prod if you want).
- Barostats: `--barostat {berendsen, monte_carlo, off}`. Berendsen is the equilibration default; Monte Carlo is the better choice for production NPT.
- Solvation: explicit (TIP3P / OPC / SPCE / TIP4P-Ew) or implicit GB. On `amber_md.py`, `--implicit-solvent {gb1, gb2, gb5, gb7, gb8}` is opt-in (default `off`); when set, `gb2` = OBC model I (igb=2) is the recommended model and GBneck2 is `gb8` (igb=8). Easy mode (`amber_run.py --mode implicit`) defaults to `gb2`. Implicit means `ntb=0, igb=N, cut=999`, no barostat.
- Engine: auto `pmemd.cuda > pmemd > sander`. `--engine` overrides.
- `--from-prmtop`: skip prep entirely when the user already has a prmtop (CHARMM-GUI, external prep). All MD entry points support it.

**Secondary core — Temperature Replica-Exchange MD**

- `amber_remd.py`: T-REMD via `pmemd.cuda.MPI -rem 1`, auto temperature ladder (geometric default; `--ladder explicit --temps "..."` for hand-tuned), per-replica mdin, groupfile, exchange-rate report parsed from `rem.log`.
- Engine: auto `pmemd.cuda.MPI > pmemd.MPI > sander.MPI`.
- Pair with `amber_analyze.py --demux-remd` to demux into per-temperature trajectories.

**Easy mode**

- `amber_run.py --mode {standard, remd, implicit}`: chains prep + min + heat + density + prod (or REMD-prod, or implicit prod) in one invocation. `--time 1ns` accepts unit suffixes. `--resume` skips already-finished stages. `--dry-run` prints all the planned commands without executing.

**Add-ons (consume MD output)**

- `amber_sp.py --mode {snapshot, trajectory}`: snapshot SP (`imin=5, maxcyc=0`) or per-frame energies via cpptraj `esander`.
- `amber_analyze.py`: cpptraj-driven RMSD / RMSF / RDF / hbond / radgyr; CSV + PNG per analysis. Optional REMD demux.
- `amber_score.py`: MMPBSA / MMGBSA endpoint binding free energy. `--method gb|pb|both`, `--per-residue`, `--alanine-scan`, `--mpi N`.

**Environment detection**

- `check_env.py`: detects AmberTools binaries (antechamber, parmchk2, tleap, sander, pmemd, pmemd.cuda, MPI variants, cpptraj, MMPBSA.py / .MPI, parmed, pdb4amber, reduce, ambpdb), Python deps (parmed, netCDF4, matplotlib), and CUDA. Ends with a `[SUMMARY]` line listing exactly which workflows the box can run.

## What v1.0 does not ship

The skill defers honestly when asked for any of these. See
`references/extension_map.md` for which script each one would land in.

- Free energy (TI / FEP / MBAR)
- Hamiltonian REMD (architecture pre-wired; `--type H` raises)
- Accelerated MD (aMD), Steered MD (SMD), umbrella sampling, metadynamics
- Biopolymer prep (ff19SB, ff14SB, OL21) — proteins, nucleic acids, complexes
- Constant-pH MD, constant-redox MD
- QM/MM
- Membrane / lipid (LIPID17)
- Multi-GPU pmemd.cuda
- PLUMED bridge
- HPC submission templates (SLURM, PBS, LSF)

## Layout

```
amber-chemist/
├── SKILL.md                 # trigger contract + method-selection tree
├── README.md                # this file
├── scripts/
│   ├── _amber.py            # shared: engine pick, mdin renderers, parsers
│   ├── check_env.py
│   ├── amber_run.py         # easy mode (standard | remd | implicit)
│   ├── amber_prep.py        # GAFF2 small-mol prep
│   ├── amber_md.py          # MD core: stages, restart, extend, implicit
│   ├── amber_remd.py        # T-REMD with auto ladder + exchange report
│   ├── amber_sp.py          # add-on: SP (snapshot / trajectory)
│   ├── amber_analyze.py     # add-on: cpptraj analysis + REMD demux
│   └── amber_score.py       # add-on: MMPBSA wrapper
├── references/
│   ├── README.md            # index
│   ├── md_core.md           # MD pipeline, restart/extend, restraints, implicit
│   ├── remd.md              # T-REMD ladder, exchange rate, demux
│   ├── force_fields.md      # GAFF2 today; ff19SB/OL21 etc. deferred
│   ├── add_ons.md           # add-on framing + extension surface
│   ├── analysis.md          # cpptraj idioms (RMSD/RMSF/RDF/hbond/radgyr)
│   ├── single_point.md      # imin=5 vs cpptraj esander
│   ├── scoring.md           # MMPBSA: GB/PB, per-residue, alanine
│   ├── failure_modes.md     # known issues + recovery
│   ├── carveout_relationship.md
│   ├── extension_map.md     # big Amber features not shipped, where they'd land
│   ├── manual_lookup.md     # URLs to Amber/cpptraj/MMPBSA manuals
│   ├── mdin_keywords.md     # most-asked mdin keywords table
│   ├── cpptraj_idioms.md    # most-asked cpptraj recipes
│   └── mmpbsa_idioms.md     # most-asked MMPBSA decks
└── evals/
    └── evals.json
```

## Relationship with `ase-chemist`

`ase-chemist` ships a v1.3 Amber carve-out (`parameterize_gaff2.py`
+ `run_amber.py`) that does GAFF2-only plain NPT small-molecule MD.
`amber-chemist` is the deeper Amber-native sibling: restart-and-extend,
REMD, implicit solvent, cpptraj-driven analysis, MMPBSA scoring. The
two skills coexist; the trigger-phrase split routes prompts to the
right one. See `references/carveout_relationship.md` for the
two-paragraph version.
