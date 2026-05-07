# mdin Keywords — Quick Reference

The ~50 mdin keywords most likely to come up in v1.0 workflows.
Anything not listed here → see the Amber Reference Manual via
`manual_lookup.md`.

Columns: keyword, typical values, what it does, manual section
(approximate; varies by edition).

## Run-control

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `imin` | `0` MD; `1` minimize; `5` SP energy only | Selects job type | §17.5 |
| `irest` | `0` start, `1` restart | Whether to read velocities from input rst7 | §17.5 |
| `ntx` | `1` no velocities; `5` read velocities | Input format flag (paired with irest) | §17.5 |
| `nstlim` | depends on `dt` and target ps | Number of MD steps | §17.5 |
| `dt` | `0.002` (with SHAKE); `0.001` (without) | MD timestep in ps | §17.5 |
| `maxcyc` | `10000` | Total min cycles (only `imin=1`) | §17.5 |
| `ncyc` | `5000` | Steepest-descent cycles before CG (`imin=1`) | §17.5 |
| `numexchg` | depends | Outer-loop count for REMD | §22 |

## Periodic-box / nonbonded

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ntb` | `0` no box; `1` constant V; `2` constant P | PBC mode | §17.5 |
| `ntp` | `0` NVT; `1` isotropic; `2` anisotropic; `3` semi-isotropic | Pressure scaling | §17.5 |
| `barostat` | `1` Berendsen; `2` Monte Carlo | Barostat algorithm (only when `ntp>0`) | §17.5 |
| `taup` | `2.0` ps | Pressure relaxation time | §17.5 |
| `cut` | `10.0` Å explicit; `999.0` implicit | Nonbonded cutoff | §17.5 |
| `iwrap` | `0` or `1` | Wrap coordinates into the primary box | §17.5 |

## Thermostat

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ntt` | `0` constant E; `1` Berendsen; `3` Langevin | Thermostat algorithm | §17.5 |
| `gamma_ln` | `2.0` 1/ps | Langevin friction coefficient | §17.5 |
| `tempi` | `0.0` for heat | Initial temperature | §17.5 |
| `temp0` | `300.0` K | Target temperature | §17.5 |
| `ig` | `-1` (random) | Random seed | §17.5 |

## SHAKE

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ntc` | `1` no SHAKE; `2` H bonds; `3` all bonds | SHAKE bond constraints | §17.5 |
| `ntf` | `1` all forces; `2` skip H; `3` skip all bonds | Force evaluation matched to ntc | §17.5 |

## Output frequency

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ntpr` | `100` or `500` | mdout print frequency (steps) | §17.5 |
| `ntwx` | `500` (= 1 ps at dt=0.002) | Trajectory write frequency | §17.5 |
| `ntwr` | `1000` or `10000` | Restart-write frequency | §17.5 |
| `ntwprt` | `0` for full system | Write only first N atoms (analysis trick) | §17.5 |
| `ioutfm` | `1` NetCDF; `0` ASCII | Trajectory format | §17.5 |

## Implicit solvent (GB)

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `igb` | `0` explicit; `1, 2, 5, 7, 8` GB models | Selects implicit-solvent flavor | §6 |
| `gbsa` | `0` off; `1` LCPO surface; `2` ICOSA | Solvent-accessible-surface term | §6 |
| `surften` | `0.005` kcal/mol/Å² | SASA proportionality | §6 |
| `saltcon` | `0.150` M | Salt concentration in GB | §6 |
| `rgbmax` | `25.0` | Max radius for Born-radius computation | §6 |

## Restraints

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ntr` | `1` to enable | Positional restraints flag | §17.6 |
| `restraintmask` | `':1-200&!@H='` | Amber mask of restrained atoms | §17.6 |
| `restraint_wt` | `10.0` kcal/mol/Å² | Force constant | §17.6 |
| `ref` | (-ref CLI flag) | Reference rst7 for restraint coordinates | §17.6 |
| `nmropt` | `0` off; `1` enables &wt and DISANG | NMR-style time-varying restraints | §28 |

## REMD / enhanced sampling

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `rem` | `0` off; `1` T-REMD | Enables replica exchange (CLI flag, not mdin) | §22 |
| `numexchg` | depends | Number of exchange attempts | §22 |
| `iamd` | `0`; `1`/`2`/`3` for aMD | Accelerated MD mode | §27 |
| `ethreshd`, `alphad`, `ethreshp`, `alphap` | depends | aMD bias parameters | §27 |
| `jar` | `0`; `1` for SMD | Steered MD flag | §28 |

## Constant-pH / redox (deferred features)

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `icnstph` | `0`; `1`/`2` for cpH-MD | Constant-pH MD flag | §29 |
| `ntcnstph` | depends | Frequency of protonation-state attempts | §29 |
| `solvph` | `7.0` | Simulated pH | §29 |
| `icnste` | `0`; `1` for cE-MD | Constant-redox MD flag | §29 |

## QM/MM (deferred)

| Keyword | Typical | What it does | Manual § |
|---|---|---|---|
| `ifqnt` | `0`; `1` to enable | QM/MM mode flag | §10 |
| `qmmask` | mask | QM region | §10 |
| `qm_theory` | `PM6`, `DFTB`, `EXTERN` | QM method | §10 |
| `qmcharge` | int | QM region charge | §10 |

## Anything not listed

→ See `manual_lookup.md` for the Amber Reference Manual link. The
keyword index in the manual's appendix is the authoritative source.

## Common mistakes

- `ntb=2, ntp=0` — incompatible (constant-P box without pressure
  scaling). Should be `ntb=2, ntp=1` for NPT.
- `ntc=2, ntf=1` — partial SHAKE. Should match (both 2, or both 1).
- `igb=2, ntb=1` — implicit and explicit can't both be on. Use
  `igb=2, ntb=0, cut=999`.
- `temp0=300` with `tempi` unset on a heat stage — the system never
  ramps. Use `tempi=0, temp0=300` plus a `&wt TEMP0` block for the
  ramp.

## Cross-reference

For runnable mdin templates with these keywords assembled, see
`scripts/_amber.py:render_min/heat/density/prod` — those are the
v1.0 templates and they cover the most common cases.
