# T-REMD Reference

Temperature Replica-Exchange MD: run N parallel MD copies at
different temperatures, attempt Metropolis exchanges between
neighboring replicas every K steps. Fixes kinetic-trapping
problems on rough free-energy surfaces (small peptides, ligand
conformational ensembles, protein folding).

## When to reach for T-REMD

- The user wants enhanced sampling and the system is small enough
  (≤ ~5000 atoms) to afford 8-16 replicas in parallel.
- Conformational ensemble of a small peptide / ligand at room
  temperature.
- Free-energy landscape mapping when single-replica MD is sticking.

## When NOT to reach for T-REMD

- Large solvated proteins (5k+ atoms × 16 replicas = a lot of
  pmemd.cuda time). Consider H-REMD or REST2 instead — both are
  v1.1+ candidates; see `extension_map.md`.
- Free-energy along a known coordinate — umbrella sampling +
  WHAM/MBAR is more efficient. v1.1+ candidate.
- The user only has one GPU. T-REMD needs MPI; minimum useful
  setup is 2-4 ranks. Check `pmemd.cuda.MPI` is on PATH first.

## Engine

T-REMD requires an MPI Amber engine: `pmemd.cuda.MPI > pmemd.MPI >
sander.MPI`. `amber_remd.py` auto-picks; override with `--engine`.
If no MPI engine is on PATH, `amber_remd.py` exits with a clear
message — do not silently fall back to single-replica MD.

## Temperature ladder

The hardest knob in T-REMD. Get this wrong and the run wastes
time — replicas don't exchange and you've just run N
uncorrelated MDs.

### Geometric ladder (v1.0 default)

```
T_i = T_low * (T_high / T_low)^(i / (N - 1))
```

Closed-form, requires no information about the system. Works well
when heat capacity is roughly constant across the range — which is
the case for small organics in water. **For protein systems with
large heat capacity, geometric over-spaces; use vdSpoel (v1.1+).**

### Patriksson-van der Spoel iterative solver (`--ladder vdspoel`)

Iteratively refines a ladder so all neighboring pairs hit a target
acceptance rate (~25%). Requires the system's number of degrees of
freedom and a target rate. **v1.0 falls back to geometric and
prints a warning**; full implementation is a v1.1 candidate.

### Explicit ladder (`--ladder explicit --temps "..."`)

You supply `--temps "300,310,320,335,350,370,395,420"`. Use this
when:

- The user has run a pilot and tuned by hand.
- Heat-capacity quirks make geometric wrong.
- Reproducing a published study.

## Exchange-rate target

| Range | Verdict |
|---|---|
| < 15% | Ladder gaps are too wide; either widen N or narrow T-range. |
| 15-50% | OK. Tighter (~25-35%) is better for sampling efficiency. |
| > 50% | Wasted GPU time — replicas are too close together. |

`amber_remd.py` parses `rem.log` after the run finishes and writes a
per-pair acceptance summary to `exchange_rate.txt`. If any pair is
outside [15%, 50%], the script prints a one-line recommendation
pointing here.

## Picking N (number of replicas)

Rule of thumb: aim for ~20% acceptance with geometric ladder. For
explicit-solvent small organics in water:

| Range (K) | Suggested N |
|---|---|
| 300-350 | 4-6 |
| 300-400 | 8 |
| 300-500 | 12-16 |

For implicit-solvent (`--implicit-solvent gb2`) you can stretch the
range or shrink N — the heat capacity is much lower so gaps space
better.

## Output layout

```
<output-dir>/
  groupfile                    # per-replica -i/-o/-c/-r/-x lines
  rem.log                      # exchange log written by pmemd
  ladder.txt                   # the temperature ladder (i\tT)
  exchange_rate.txt            # parsed acceptance rates per pair
  replica_00/{prod.in, prod.mdout, prod.nc, prod.rst7}
  replica_01/...
  ...
```

Each replica owns a directory; pmemd writes its trajectory and rst7
into that directory.

## Demuxing into per-temperature trajectories

`amber_remd.py` does **not** demux — that lives in `amber_analyze.py`
because not every REMD run needs it (e.g. user only cares about the
lowest-T replica). Run:

```bash
python scripts/amber_analyze.py --demux-remd \
    --remd-dir <remd-out> --prmtop sys.prmtop --output-dir demuxed/
```

Internally this uses cpptraj's `ensemble` keyword:

```
parm sys.prmtop
ensemble remd_out/replica_00/prod.nc remd_out/replica_01/prod.nc ...
autoimage
trajout demuxed/demux.nc nobox
run
```

cpptraj reads all replicas in lockstep and writes per-temperature
trajectories so you can analyze each temperature independently.

## Common failure modes

See `failure_modes.md` for the consolidated list. Highlights:

- **Acceptance rate is 0** for some pairs — usually one replica
  diverged early. Inspect `replica_NN/prod.mdout` for NaN or
  exploded forces.
- **MPI launch fails** — `mpirun -np N` count must equal
  `--n-replicas`. If using `srun`, pass `--mpiexec srun` and
  configure `SLURM_NTASKS` upstream.
- **Box size mismatch across replicas** — REMD requires identical
  topology and box for all replicas; you cannot mix `solvateBox` and
  `solvateOct` outputs.
- **`--exchange-every` too low (<100)** — most exchanges fail
  because the replica hasn't decorrelated; pmemd guidance is
  500-2000 steps between attempts. `amber_remd.py` warns at <100.

## Reference manual

For pmemd's REMD specifics (exchange protocol, file naming, MPI
options), see Amber Reference Manual §22 ("Replica exchange
molecular dynamics"). Linked from `manual_lookup.md`.
