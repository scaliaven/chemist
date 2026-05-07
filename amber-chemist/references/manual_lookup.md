# Manual & Reference Lookup

Curated URLs for authoritative Amber documentation. Use these
liberally — if the answer to "what does this mdin keyword do?" or
"what are the options for this MMPBSA block?" is in here, cite it.

## Primary references

### Amber Reference Manual (PDF)
The canonical source for mdin keywords, force-field options, file
formats, and protocol guidance.

URL: <https://ambermd.org/Manuals.php> → "Amber 2024 Reference Manual"
(or the latest year). Free since AmberTools25.

How to cite: "Reference Manual §17.5 for the `nmropt` keyword" —
section numbers are stable across recent editions.

### AmberHub (community Q&A)
Searchable archive of user questions, answers, and protocol
discussion. The first place to look when the manual is terse.

URL: <https://amberhub.chpc.utah.edu/>

How to cite: "AmberHub thread <topic>" or paste the URL.

### AmberMD tutorials
Hands-on step-by-step protocols. Useful when explaining "why this
stage at this temperature for this duration" — the tutorials show
the canonical Amber community defaults.

URL: <https://ambermd.org/tutorials/>

### cpptraj manual (PDF)
Bundled with AmberTools at:

```
$AMBERHOME/AmberTools/src/cpptraj/doc/cpptraj.pdf
```

Online mirror at AmberHub. Authoritative for cpptraj actions and
analysis syntax.

### MMPBSA.py guide (PDF)
Bundled with AmberTools at:

```
$AMBERHOME/doc/MMPBSA.pdf
```

Authoritative for `&general / &gb / &pb / &decomp / &alanine_scanning`
block keywords.

Also: `MMPBSA.py -h` prints a summary of the most-used flags.

### GAFF2 / antechamber documentation
URL: <https://ambermd.org/antechamber/gaff.html>

Includes the GAFF2 atom types, bonded parameters, and recommended
charge methods.

### AmberTools changelog
URL: <https://ambermd.org/AmberTools.php>

Cite when a feature is version-gated. AmberTools25 is the current
fully-open-source release as of this skill's authoring (2026).

## Secondary references

### Force-field papers (cite for "why this force field")
- **GAFF2**: Wang et al. 2004 (original GAFF), Vassetti et al. 2019 (GAFF2). See `references/force_fields.md`.
- **AM1-BCC**: Jakalian et al. 2002 (J. Comp. Chem.).
- **ff19SB**: Tian et al. 2020 (J. Chem. Theory Comput.).
- **OL21**: Galindo-Murillo et al. 2016 (OL15) extended to RNA in AmberTools25.
- **OPC water**: Izadi et al. 2014.
- **TIP3P**: Jorgensen et al. 1983 — the original water model paper.

### Methodology papers (cite for "why this method")
- **MMPBSA review**: Genheden & Ryde 2015 (Expert Opin. Drug Discov.).
- **T-REMD ladder tuning**: Patriksson & van der Spoel 2008 (PCCP).
- **Monte Carlo barostat in pmemd**: Steinbrecher et al. 2012.
- **GBneck2**: Nguyen et al. 2013.

## How to cite from this skill

When the model writes a Python script that includes `igb=2` or
`barostat=2`, it should be able to say *why* by pointing at the
table in `mdin_keywords.md` (which in turn cites the manual). For
example:

> "Setting `barostat=2` enables Monte Carlo barostat — better than
> Berendsen for production NPT. See `references/mdin_keywords.md`
> and Reference Manual §17.6."

This is the difference between a skill that mechanically renders
mdins and one that helps the user understand what they're running.

## When the manual disagrees with this skill

The manual wins. If you find a place where this skill's reference
files contradict the Amber Reference Manual, the manual is the
authoritative source — file an issue or update the reference file.

## What is NOT here

- **Application-specific protocols** (e.g. "how do I set up a kinase
  simulation?") — those live in the AmberMD tutorials.
- **Algorithm internals** — `pmemd` integrator details, GB Born
  radii calculation, etc. — see the source code or the
  Computational Methods chapter of the Reference Manual.
- **Force-field development guidance** — out of scope for a workflow
  skill.
