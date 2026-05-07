# MMPBSA Idioms — Recipe Book

Drop-in MMPBSA `.in` decks for the most common scoring jobs. Each
idiom shows the deck plus the matching `MMPBSA.py` invocation.

## Standard 3-prmtop layout

Every MMPBSA job needs **gas-phase** prmtops for:

- **Complex** (`-cp`): receptor + ligand, no waters / ions.
- **Receptor** (`-rp`): receptor only.
- **Ligand** (`-lp`): ligand only.

Plus a trajectory of the complex (`-y`). If the trajectory has
explicit waters, also pass `-sp <solvated.prmtop>` so MMPBSA.py
knows what to strip per-frame.

## GB-only (MMGBSA, fast)

`mmgbsa.in`:
```
MMGBSA endpoint scoring (GB only, igb=2, 0.15 M)
&general
  startframe=1, endframe=0, interval=1, keep_files=0,
/
&gb
  igb=2, saltcon=0.150,
/
```

Invocation:
```bash
MMPBSA.py -O -i mmgbsa.in -cp com.prmtop -rp rec.prmtop -lp lig.prmtop -y prod.nc
```

`amber_score.py --method gb` renders this. Default `--gb-model 2`
matches `igb=2`.

## PB-only (MMPBSA)

`mmpbsa.in`:
```
MMPBSA endpoint scoring (PB only, mbondi2 radii, 0.15 M)
&general
  startframe=1, endframe=0, interval=1, keep_files=0,
/
&pb
  istrng=0.150, radiopt=0, inp=1,
/
```

`radiopt=0` uses prmtop's mbondi2 radii (set during prep). `inp=1`
adds nonpolar contribution from SASA.

## GB + PB combined

Both `&gb` and `&pb` blocks in the same deck. MMPBSA.py reports both
ΔG values; useful for cross-checking.

## Per-residue decomposition

Add `&decomp`:
```
&decomp
  idecomp=2, dec_verbose=1,
/
```

| `idecomp` | Meaning |
|---|---|
| 1 | per-residue, intra-only |
| 2 | per-residue, including pairs (recommended) |
| 3 | adds backbone/sidechain split |
| 4 | full pair-residue decomposition |

`dec_verbose=1` prints per-residue components in `FINAL_DECOMP_*.dat`.

## Computational alanine scan

Add `&alanine_scanning`:
```
&alanine_scanning
/
```

(No parameters needed.) MMPBSA.py mutates each interface residue to
alanine in silico and re-evaluates the binding energy. The
"ΔΔG_ala" tells you which residues contribute most to binding.

Common scope-narrowing: combine with `&general start/end` to focus
on a particular interface region, or use ParmEd to manually
pre-truncate the prmtop to interface-only residues.

## MPI variant

`amber_score.py --mpi 4` switches to `MMPBSA.py.MPI` and prepends
`mpirun -np 4`. The deck is unchanged; MMPBSA.py.MPI distributes
frames across ranks.

If `MMPBSA.py.MPI` is not on PATH, the script hard-fails. Check
`python check_env.py` first.

## Stride for long trajectories

For 1 µs trajectories, even GB MMPBSA is slow. Stride to a
manageable count:

```
&general
  startframe=1, endframe=0, interval=10, keep_files=0,
/
```

`interval=10` = every 10th frame. Aim for ~1000 frames total for
reasonable error bars.

## Quasi-harmonic entropy (`entropy=1` in &general)

```
&general
  startframe=1, endframe=0, interval=1, keep_files=0, entropy=1,
/
```

Adds a quasi-harmonic estimate of -TΔS_conf. Cheap (does not need
new MD); correlates poorly with NMA (normal-mode analysis) which is
the rigorous-but-expensive alternative. Use for comparative ranking;
do not report absolute ΔG_bind from QH-entropy.

`entropy=2` runs NMA at the cost of ~10x runtime.

## Common deck recipes

### Drug-binding (typical druglike-ligand against protein receptor)
- GB only, `igb=2`, salt 0.15 M, all frames.
- → `amber_score.py --method gb --gb-model 2`

### Hot-spot identification
- GB + alanine scan; cite the per-residue ΔΔG_ala.
- → `amber_score.py --method gb --alanine-scan`

### Antibody-antigen with high charge
- PB only (or GB+PB), salt at the experimental ionic strength,
  per-residue decomp.
- → `amber_score.py --method both --per-residue --ionic-strength 0.150`

### Quick screening across a series
- GB only, stride to ~500 frames, MPI x4 if available.
- → `amber_score.py --method gb --stride 5 --mpi 4`

## Output

```
mmpbsa/
  <prefix>.in                    # MMPBSA input deck
  FINAL_RESULTS_MMPBSA.dat       # primary output
  FINAL_DECOMP_MMPBSA.dat        # if --per-residue
  ALANINE_SCAN.dat               # if --alanine-scan
  <prefix>_summary.json          # parsed delta-G + metadata
  ... (additional MMPBSA.py outputs if --keep-files)
```

`<prefix>_summary.json` is parsed by `amber_score.py` for easy
machine consumption.

## Common errors (cross-reference with `failure_modes.md`)

- "Topology mismatch between -cp and -y" — trajectory is from a
  different system.
- "No frames after stripping" — `--solvated-prmtop` not set.
- "alanine_scan finds no residues" — interface residues not in both
  ligand/receptor selections.

## Reference manual

MMPBSA.py guide: `$AMBERHOME/doc/MMPBSA.pdf`. Also `MMPBSA.py -h`.
See `manual_lookup.md`.
