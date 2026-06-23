# MD Core (v1.0) — Single-Replica MD Pipeline

The MD core is the load-bearing v1.0 verb. Everything in this skill
either feeds the MD core (prep) or consumes its output (add-ons).

## Pipeline shape

```
amber_prep.py    →    prmtop + rst7   (one molecule, one .pdb/.mol2/.xyz)
                          │
                          ▼
amber_md.py --stage min               # 10000-cycle minimization
amber_md.py --stage heat --restart   # 50 ps NVT 0→T (default)
amber_md.py --stage density --restart # 100 ps NPT, barostat
amber_md.py --stage prod --restart    # production NPT (or NVT for implicit)
                          │
                          ▼
                     prod.nc trajectory  →  add-ons
```

`amber_run.py --mode standard` wires this pipeline together; reach for
`amber_md.py` directly for stage-level control.

## Stage defaults (amber_md.py)

| Stage | mdin idiom | Default n-steps | Notes |
|---|---|---|---|
| min | `imin=1, maxcyc=10000, ncyc=5000` | n/a (uses --maxcyc) | Steepest descent for `ncyc` cycles, then conjugate gradient. |
| heat | `imin=0, irest=0, ntx=1, nstlim=N, ntb=1, ntp=0, ntc=2, ntf=2, ntt=3, gamma_ln=2.0` | 25000 (50 ps at 2 fs) | 0 → T linear ramp via `&wt TEMP0` block. SHAKE on H bonds. |
| density | `imin=0, irest=1, ntx=5, nstlim=N, ntb=2, ntp=1` | 50000 (100 ps at 2 fs) | Berendsen by default; `--barostat monte_carlo` flips to `barostat=2`. |
| prod | `imin=0, irest={0,1}, ntx={1,5}, nstlim=N, ntb=2, ntp=1` | 250000 (500 ps at 2 fs) | NPT default; flips to NVT when `--implicit-solvent`. |
| custom | Whatever you pass via `--mdin <file>` | n/a | Escape hatch. |

## Restart (`--restart`) vs Extend (`--extend`)

These verbs do different things; do not confuse them.

**`--restart`** — chain a *different* stage from a previous stage's
rst7. Sets `irest=1, ntx=5` so velocities are read in. Used for
heat → density → prod chaining. Output `<prefix>.{mdin,mdout,rst7,nc}`.

**`--extend`** — chain another chunk of the *same* stage. Auto-numbers
the output: if `prod.rst7` and `prod.mdout` (with "Total wall time")
already exist, the new chunk is `prod_2.{nc,rst7,mdout}`, then `_3`,
etc. Reads from the most recent completed chunk's rst7. Use this for
"run another N ps from where prod left off."

A common mistake: trying to use `--restart` to extend prod. That
overwrites `prod.{nc,rst7,mdout}` and loses the previous chunk's
trajectory. Always use `--extend` for same-stage continuation.

## Restraints

`--restraint-mask <amber-mask>` + `--restraint-weight <kcal/mol/Å²>`
adds positional-restraint keywords to the `&cntrl` namelist (Amber has no
separate `&restraint` namelist for these):

```
ntr=1, restraintmask='@CA,C,N&!@H=', restraint_wt=10.0,
```

Common patterns:

- Backbone restraint during heat/density: `'@CA,C,N&!@H='` at 10 kcal/mol/Å².
- All heavy atoms during heat: `'!@H='` at 5 kcal/mol/Å².
- Solute heavy atoms only (skip waters): `':!WAT&!@H='`.

You also need to pass `--ref <reference.rst7>` so pmemd uses the right
reference coordinates for the harmonic restraint.

## Implicit-solvent MD (GB)

`--implicit-solvent {gb1, gb2, gb5, gb7, gb8}` swaps the explicit
periodic-box mdin block for `ntb=0, igb=N, cut=999.0`. Effects:

- No PBC, so no barostat (whatever `--barostat` you pass is ignored).
- Cutoff effectively infinite (`cut=999`).
- `--stage density` is meaningless and refuses to run.
- Recommended for fast small-peptide sampling and for the GB-MD legs
  of binding studies where explicit-solvent is too expensive.

`igb=2` (OBC model I) is the v1.0 default — Onufriev's well-validated
GB model for small peptides. `igb=8` (GBneck2) is the most modern, most
expensive. See `mdin_keywords.md` for the full pricing table.

## Barostats

`--barostat {berendsen, monte_carlo, off}`:

- **Berendsen** (default) — fast and stable for equilibration; produces
  the wrong NPT distribution. Fine for density equilibration; not
  recommended for production NPT averages.
- **Monte Carlo** (`barostat=2` in mdin) — correct NPT distribution,
  rejection-based volume scaling. Use for production NPT.
- **off** — NVT mode (`ntb=1, ntp=0`). Used by REMD prod and implicit-
  solvent runs.

## When to use `--mdin <file>` (custom stage)

When the user has bespoke needs the standard renderers don't cover:
non-standard `&wt` annealing schedules, NMR restraints (`nmropt=1`
+ DISANG file), aMD bias parameters, PLUMED hooks. Pass the file with
`--stage custom --mdin <file>`; the script does no template
substitution, just routes the file at pmemd.

## What this core does NOT do

- **REMD** — use `amber_remd.py`.
- **Free energy** — TI / FEP / MBAR are not in v1.0; see `extension_map.md`.
- **aMD / SMD / umbrella** — mdin-flag changes; planned shape is `amber_md.py --boost {amd,smd,umbrella}`; see `extension_map.md`.
- **Constant-pH MD** — `amber_cpH.py` would land separately; see `extension_map.md`.
- **Multi-GPU pmemd.cuda** — single-GPU only in v1.0; see `extension_map.md`.

## Common failure modes

See `failure_modes.md` for the consolidated list. Highlights:

- "tleap reported success but prmtop missing" — usually antechamber failed silently because `--net-charge` was wrong. Re-run `amber_prep.py --keep-intermediates`.
- "pmemd.cuda OOM at start of prod" — water box too large for the GPU; reduce `--buffer` from 14 Å to 10 Å, or switch to pmemd (CPU).
- "Density never settles" — solute is in a void; the system needs heat with restraints first. Use `--restraint-mask '!@H='` during heat.
