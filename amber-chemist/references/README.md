# amber-chemist References — Index

Reference files are topic-scoped: read the one matching your task,
not the whole index. The MD core, REMD, and add-ons are the
load-bearing distinctions; everything else is supporting material or
honest deferrals.

## When to read which file

### Core (read these first when running MD)

- [`md_core.md`](md_core.md) — The single-replica MD pipeline: stage rendering, restart vs extend, restraints, barostat options, implicit-solvent (GB) MD. Read when running `amber_md.py` or chaining stages by hand.
- [`remd.md`](remd.md) — T-REMD: temperature ladder choice (geometric vs vdSpoel vs explicit), exchange-rate target (15-50%), engine selection (`pmemd.cuda.MPI -rem 1`), demux. Read when running `amber_remd.py` or before tuning a ladder.
- [`force_fields.md`](force_fields.md) — Force-field choices: GAFF2 + AM1-BCC (v1.0 only), water models, what's deferred (ff19SB, OL21, LIPID17). Read when the prompt names a biopolymer force field.

### Add-ons (read when consuming MD output)

- [`add_ons.md`](add_ons.md) — The framing: add-ons consume the MD output, not co-equal verbs. The extension surface convention.
- [`analysis.md`](analysis.md) — cpptraj idioms used by `amber_analyze.py` (RMSD, RMSF, RDF, hbond, radgyr, ensemble for REMD demux).
- [`single_point.md`](single_point.md) — `imin=5, maxcyc=0` snapshot SP vs cpptraj `esander` per-frame energies.
- [`scoring.md`](scoring.md) — MMPBSA / MMGBSA: input file structure, GB vs PB, alanine scan, per-residue. What MMPBSA is **not**.

### Reference / lookup

- [`manual_lookup.md`](manual_lookup.md) — Curated URLs to the Amber Reference Manual, AmberHub, tutorials, cpptraj/MMPBSA PDFs. The fast path to authoritative answers.
- [`mdin_keywords.md`](mdin_keywords.md) — Flat table of the ~50 most-asked mdin keywords with manual section pointers.
- [`cpptraj_idioms.md`](cpptraj_idioms.md) — Drop-in cpptraj recipes for the most common analyses.
- [`mmpbsa_idioms.md`](mmpbsa_idioms.md) — Drop-in MMPBSA decks (GB, PB, alanine, per-residue, MPI).

### Failure modes / deferrals / context

- [`failure_modes.md`](failure_modes.md) — Known failure modes across prep / MD / REMD / analysis / scoring, with recovery recipes.
- [`extension_map.md`](extension_map.md) — Big Amber features not yet shipped (TI/FEP, aMD, SMD, umbrella, H-REMD, QM/MM, constant-pH, membrane, PLUMED, multi-GPU): which script each one would land in. Cite this for honest deferrals.
- [`carveout_relationship.md`](carveout_relationship.md) — How `amber-chemist` relates to `ase-chemist`'s v1.3 carve-out. Cite when the user is on a shared-zone prompt and wonders which skill should answer.
