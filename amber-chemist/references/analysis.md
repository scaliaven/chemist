# Analysis Reference (cpptraj idioms used by `amber_analyze.py`)

`amber_analyze.py` builds a cpptraj input deck from `--analyses` and
runs `cpptraj -i <deck>`. Each requested analysis writes a `.dat`
file that the script post-processes into CSV + PNG.

## Standard preamble

Every deck starts with:

```
parm <prmtop>
reference <reference.rst7>          # optional; defaults to first frame
trajin <trajectory> 1 last <stride>
autoimage
```

`autoimage` re-wraps molecules across the periodic box so RMSD /
RMSF aren't fooled by jumping atoms. Mandatory for any periodic
trajectory.

## RMSD

```
rms first @CA,C,N&!@H= out rmsd.dat
```

- `first` aligns each frame to the first frame; `reference` aligns to the loaded reference.
- Mask defaults to `@CA,C,N&!@H=` (backbone heavy atoms). For ligand RMSD: `:LIG&!@H=`.
- Output: 2-column dat (frame, RMSD in Å).

## RMSF (per-residue)

```
atomicfluct out rmsf.dat @CA,C,N&!@H= byres
```

- `byres` aggregates per-residue RMSF.
- Default mask is heavy-atom backbone; pass `--rmsf-mask` for sidechains.
- Output: 2-column dat (residue, RMSF in Å).

## RDF (radial distribution)

```
rdf out rdf.dat 0.1 10.0 :WAT@O :LIG
```

- Bin width 0.1 Å, max r 10 Å.
- First mask is the central group; second is the surrounding group.
- Common pairs:
  - Water around ligand: `:WAT@O :LIG`
  - Water-water: `:WAT@O :WAT@O`
  - Ion around protein: `:Na+ :CA`

## Hydrogen bonds

```
hbond donormask :1-200&!@H= acceptormask :1-200&!@H= out hbond.dat
```

- Default angle/distance cutoffs: 135° / 3.0 Å.
- `donormask` and `acceptormask` should be polar atoms. Wildcards (`*`) include all.
- Output: 2-column dat (frame, hbond count); plus per-hbond breakdown to `hbond.dat.avg`.

## Radius of gyration

```
radgyr out rg.dat
```

- No mask = whole system. Pass an explicit mask to restrict (e.g. `radgyr :1-200 out rg.dat`).
- Output: 2-column dat (frame, Rg in Å).

## Per-frame energy decomposition (esander)

For per-frame energies, use `amber_sp.py --mode trajectory` rather
than `amber_analyze.py`. The cpptraj idiom under the hood:

```
esander mysander out energies.dat
```

`mysander` is the data-set label; `out energies.dat` writes a
9-column dat (frame + 8 energy components: VDW, EEL, BOND, ANGLE,
DIHED, EELEC14, VDW14, RESTRAINT or similar depending on system).

## REMD demux (ensemble keyword)

```
parm sys.prmtop
ensemble remd_out/replica_00/prod.nc remd_out/replica_01/prod.nc ... remd_out/replica_07/prod.nc
autoimage
trajout demuxed/demux.nc nobox
run
```

cpptraj's `ensemble` reads all replicas in lockstep, sorts each frame
by which replica is currently at which temperature (using rem.log),
and writes per-temperature trajectories. `amber_analyze.py
--demux-remd` orchestrates this.

`nobox` is required when writing demuxed trajectories to NetCDF if
the box parameters differ across replicas.

## Stripping waters / ions

For analyses that don't need the solvent (e.g. ligand RMSD,
secondary structure), strip waters first:

```
strip :WAT,Na+,Cl-
```

After `autoimage` and before the analysis. Reduces memory footprint
and speeds up cpptraj significantly on large boxes.

## Output shape

`amber_analyze.py` post-processes each `.dat` into:

- `<prefix>_<analysis>.csv` — CSV with the dat header.
- `<prefix>_<analysis>.png` — matplotlib line plot (frame vs value).

This matches `ase-chemist/scripts/analyze_traj.py`'s shape so
users get consistent file layouts across the two skills.

## Common failure modes

- "RMSD never converges" — usually the reference frame is bad.
  Try `--reference <equilibrated_rst7>` instead of frame-1 default.
- "RDF is flat" — the masks don't overlap. Check with `cpptraj`
  interactively first.
- "esander fails with 'no nonbonded params'" — the prmtop has bad
  GAFF2 typing. Re-run `amber_prep.py` with `--keep-intermediates`
  and check `parmchk2`'s `.frcmod` output.
- "ensemble fails with 'topology mismatch'" — REMD requires
  identical topology across replicas; you cannot mix solvateBox /
  solvateOct outputs.

## Reference manual

cpptraj manual is bundled with AmberTools at
`$AMBERHOME/AmberTools/src/cpptraj/doc/cpptraj.pdf`. Online mirror
at AmberHub. Linked from `manual_lookup.md`.

For more cpptraj recipes (clustering, secondary structure,
dihedral analysis), see `cpptraj_idioms.md`.
