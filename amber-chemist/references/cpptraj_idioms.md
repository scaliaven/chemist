# cpptraj Idioms — Recipe Book

Drop-in cpptraj snippets for the analyses most commonly asked of
this skill. Anything not listed → see the cpptraj manual via
`manual_lookup.md`.

## Standard preamble

```
parm sys.prmtop
trajin prod.nc 1 last 1
autoimage
```

`autoimage` re-wraps molecules across PBC; mandatory for any
periodic-box trajectory.

## RMSD (vs first frame)

```
rms first @CA,C,N&!@H= out rmsd.dat
```

Variants:

- vs reference: `reference equilibrated.rst7` (before trajin), then `rms reference @CA,C,N out rmsd.dat`
- ligand only: `rms first :LIG&!@H= out lig_rmsd.dat`
- backbone-aligned but ligand RMSD: two-pass; align on backbone first

## RMSF (per-residue or per-atom)

```
atomicfluct out rmsf.dat byres
```

- `byres` = per-residue (recommended).
- `byatom` = per-atom (huge file).
- Add a mask: `atomicfluct @CA out ca_rmsf.dat`.

## RDF

```
rdf out rdf_water_lig.dat 0.1 10.0 :WAT@O :LIG
```

- Bin width 0.1 Å; max 10 Å.
- First mask = central group; second = surrounding.
- Common pairs:
  - water-ligand: `:WAT@O :LIG`
  - water-water: `:WAT@O :WAT@O`
  - ion-protein: `:Na+ :CA`

## Hydrogen bonds

```
hbond donormask :1-200&!@H= acceptormask :1-200&!@H= out hbond.dat
```

- Defaults: 135° angle / 3.0 Å distance.
- Wildcard `*` = all polar atoms.
- Output: 2-column dat (frame, total hbond count); per-hbond breakdown
  in `hbond.dat.avg`.

## Radius of gyration

```
radgyr out rg.dat
```

- Add a mask: `radgyr :1-200 out rg.dat` (only residues 1-200).

## Per-frame energy decomposition (esander)

```
esander myset out energies.dat
```

- `myset` is the data-set label.
- Output: 9-column dat (frame + 8 energy components).
- Used by `amber_sp.py --mode trajectory`.

## REMD demux (ensemble keyword)

```
parm sys.prmtop
ensemble remd_out/replica_00/prod.nc remd_out/replica_01/prod.nc remd_out/replica_02/prod.nc remd_out/replica_03/prod.nc remd_out/replica_04/prod.nc remd_out/replica_05/prod.nc remd_out/replica_06/prod.nc remd_out/replica_07/prod.nc
autoimage
trajout demuxed/demux.nc nobox
run
```

`nobox` is required when writing demuxed trajectories to NetCDF.

## Stripping waters / ions

```
strip :WAT,Na+,Cl-
```

After `autoimage`, before the analysis. Reduces memory significantly
on large explicit-solvent boxes.

For a stripped *output* trajectory, also write a stripped prmtop:

```
parmstrip :WAT,Na+,Cl- outparm sys_dry.prmtop
```

(`outparm` is a parmed action; cpptraj has the equivalent.)

## Conformational clustering (extension candidate)

```
cluster hieragglo averagelinkage epsilon 2.0 out clusters.dat \
    summary clusters_summary.dat repout cluster_rep repfmt pdb
```

- `epsilon 2.0` = RMSD cutoff 2.0 Å for cluster merge.
- `repout cluster_rep` writes representative pdbs per cluster.
- Will land in `amber_analyze.py --cluster` (see `extension_map.md`).

## Secondary structure (extension candidate)

```
secstruct :1-200 out dssp.dat sumout dssp_summary.dat
```

- Mask = protein residues.
- Output: per-frame per-residue DSSP code.
- Will land in `amber_analyze.py --dssp`.

## Dihedral analysis

```
multidihedral phi psi resrange 1-200 out dihedrals.dat
```

- `phi psi` = standard backbone dihedrals.
- `resrange 1-200` = residue range.

## Distance / angle / torsion

```
distance d1 :1@CA :200@CA out distances.dat
angle a1 :1@CA :100@CA :200@CA out angles.dat
torsion t1 :1@CA :2@CA :3@CA :4@CA out torsions.dat
```

## NMR-style ensemble averages

```
average prod_avg.pdb pdb
```

Writes a pdb of the average structure. Useful for "what does the
typical conformation look like?"

## Native contacts

```
nativecontacts :1-100 :100-200 mindist out nc.dat
```

Counts contacts between two residue ranges that exist in the
reference frame.

## Common cpptraj options

- `1 last 1` — frame 1 to last with stride 1 (everything).
- `::10` — stride 10 (every 10th frame).
- `1 1000 5` — frames 1-1000, stride 5.
- `last 1000 1` — last 1000 frames.

## Why use cpptraj over MDAnalysis or nglview?

- **Speed**: cpptraj is C++; MDAnalysis is Python. For large
  trajectories (>1 GB), the difference is hours vs seconds.
- **Native Amber support**: cpptraj reads NetCDF-Amber and prmtop
  natively; nothing to convert.
- **`esander`**: per-frame energy decomposition through pmemd's
  energy code. No Python equivalent.
- **`ensemble`**: REMD demux. No Python equivalent.

For protein-specific analysis (per-residue secondary structure
timelines, contact maps with selection-language queries), MDAnalysis
is more flexible. v1.0 stays cpptraj-only because that's where the
Amber-native idioms live.

## Reference manual

cpptraj manual: `$AMBERHOME/AmberTools/src/cpptraj/doc/cpptraj.pdf`.
Online mirror at AmberHub. See `manual_lookup.md`.
