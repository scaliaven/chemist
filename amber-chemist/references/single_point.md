# Single-Point Energy Reference

`amber_sp.py` ships two modes for "give me an energy from this
prmtop":

| Mode | Reads | Writes | Engine |
|---|---|---|---|
| `snapshot` | `.prmtop`, `.rst7` | `<prefix>.json` | pmemd / sander (`imin=5, maxcyc=0`) |
| `trajectory` | `.prmtop`, `.nc` | `<prefix>_energies.dat` | cpptraj `esander` action |

## When to use which

- **One frame** (snapshot of an equilibrated structure) → `snapshot`.
- **Many frames** (per-frame energy series across a trajectory) → `trajectory`.

The two paths produce comparable energies but go through different
engines: `imin=5` runs the standard pmemd integrator with one
energy evaluation; `esander` invokes pmemd's energy code through
cpptraj. For systems pmemd can run, both produce the same numbers
to ~6 decimal places.

## Snapshot mode

```bash
python amber_sp.py --mode snapshot \
    --prmtop sys.prmtop --rst run/heat.rst7 \
    --output-prefix heat_sp --output-dir analysis/
```

Writes `heat_sp.in` (mdin) with:

```
&cntrl
  imin=5, maxcyc=0,
  ntb=1, cut=10.0,
  ntpr=1, ntwx=0,
&end
```

Runs the engine (`pmemd.cuda > pmemd > sander`), parses the mdout's
last `NSTEP` block (the only one when `maxcyc=0`), and writes a
JSON summary:

```json
{
  "mode": "snapshot",
  "prmtop": "...",
  "rst": "...",
  "energy_kcal_per_mol": -42173.5,
  "decomposition": {
    "BOND": 12.3,
    "ANGLE": 45.6,
    "DIHED": 78.9,
    "VDWAALS": -1234.5,
    "EEL": -41067.8,
    "EHBOND": 0.0,
    "RESTRAINT": 0.0,
    "VOLUME": 28453.7,
    "DENSITY": 1.005,
    "TEMP": 0.0
  }
}
```

`TEMP` is 0 because `imin=5, maxcyc=0` doesn't propagate dynamics
— it just evaluates the potential at the loaded coordinates.

## Trajectory mode

```bash
python amber_sp.py --mode trajectory \
    --prmtop sys.prmtop --trajectory run/prod.nc \
    --frames "::10" \
    --output-prefix prod_per_frame --output-dir analysis/
```

Writes `prod_per_frame.cpptraj`:

```
parm sys.prmtop
trajin run/prod.nc ::10
esander prod_per_frame out prod_per_frame_energies.dat
go
quit
```

`::10` is cpptraj's frame-slice syntax (start::stride::end);
`::10` means every 10th frame. Common patterns:

- `1 last` — every frame.
- `::10` — every 10th frame.
- `1 1000 5` — frames 1-1000 stride 5.
- `last 1000 1` — last 1000 frames.

Output `prod_per_frame_energies.dat` has columns:

```
#Frame  prod_per_frame[bond]  [angle]  [dihed]  [vdw]  [eel]  [vdw14]  [eel14]  [eptot]
```

## When `esander` fails

The `esander` action re-runs sander internally to compute energies.
It needs:

- A valid `.prmtop`. If the prmtop has bad GAFF2 typing, `esander`
  errors with "no nonbonded params" or similar. Re-run
  `amber_prep.py --keep-intermediates` and check the `.frcmod` /
  `.mol2`.
- Periodic-box info if the trajectory has waters. Ensure the
  trajectory is autoimaged or include `autoimage` before `esander`.
- A consistent topology. If you stripped waters from the trajectory
  (`strip :WAT`) you also need a stripped prmtop (use
  `parmed`'s `strip` then `outparm`).

## Endpoint binding free energy ≠ single-point

A common confusion: "compute the binding energy of this complex" is
**not** a single-point job. It's a three-trajectory MMPBSA / MMGBSA
calculation; use `amber_score.py`. Single-point gives you the
internal energy of one configuration, which is not a binding free
energy.

## Reference manual

- `imin=5, maxcyc=0`: Amber Reference Manual §17.5 (Energy minimization).
- `esander` action: cpptraj manual §"esander".

See `manual_lookup.md` for current URLs.
