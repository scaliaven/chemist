# Gaussian Reference (v1.4 — DFT SP / Opt / Freq)

This file replaces the v2 stub. v1.4 ships:

- `scripts/gaussian_sp.py` — DFT single-point energy + forces + dipole
  via `ase.calculators.gaussian.Gaussian`. Optional cclib parse for
  Mulliken/Löwdin/Hirshfeld charges and HOMO/LUMO eigenvalues.
- `scripts/gaussian_opt.py` — DFT geometry optimization via
  `GaussianOptimizer` (delegates to Gaussian's L103 internal optimizer
  in one g16/g09 invocation, ~10–100× faster than wrapping ASE BFGS
  around per-step Gaussian SP calls).
- `scripts/gaussian_freq.py` — DFT frequency + thermochemistry
  (vib_freqs / ZPE / enthalpy / Gibbs G), parsed via **cclib**. ASE's
  `read_gaussian_out` does not parse vibrational frequencies, so cclib
  is a hard dependency for this script.

All three scripts run **through ASE** in the standard Calculator pattern
(`atoms.calc = Gaussian(...)`, `atoms.get_potential_energy()` /
`GaussianOptimizer(atoms, calc).run(...)`). The g16/g09 binary runs as
a subprocess managed by ASE's `FileIOCalculator` machinery — same
orchestration model as MACE, tblite, EMT, etc. **No carve-out.**

## §1. Method-selection rules

Apply in order. The first rule that fits is your answer.

1. **The user explicitly named a DFT method** (B3LYP, ωB97X-D, M06-2X,
   PBE0, ...) or asked for DFT/CCSD/post-HF accuracy → use Gaussian.
2. **The user wants quantitative thermochemistry** (ZPE, enthalpy,
   Gibbs free energy at ~few-kcal/mol accuracy) → optimize with
   `gaussian_opt.py --convergence tight`, then run `gaussian_freq.py`
   at the same method/basis.
3. **The system is a transition-metal complex and GFN1/GFN2-xTB
   underperformed** → use Gaussian with a TM-appropriate functional
   (PBE0-D3(BJ) or TPSSh-D3 with def2-TZVP).
4. **The user wants HOMO/LUMO at DFT level** rather than the raw xTB
   eigenvalue gap → use `gaussian_sp.py` with cclib installed. cclib
   parses MO eigenvalues from the .log; report eV directly.
5. **Otherwise stay on xTB.** Gaussian jobs cost minutes-to-hours;
   `single_point.py --calculator xtb` costs seconds. The skill should
   recommend Gaussian only when DFT is actually needed, not as a
   default upgrade.

## §2. The no-defaults policy

`gaussian_sp.py`, `gaussian_opt.py`, and `gaussian_freq.py` all
**require** `--method`, `--basis`, `--charge`, `--multiplicity`, `--mem`,
and `--nproc`. There are no defaults and the scripts will refuse to
run without them. This is deliberate — silently picking a default has
been the wrong-physics failure mode v1 already guards against
elsewhere (EMT on an organic, wrong multiplicity in xTB).

When the user asks "what should I use?", recommend a defensible choice
and have them confirm before running:

- **Organic SCF** — `wB97XD / def2tzvp`. Outperforms B3LYP-D3 across
  GMTKN55 (Mardirossian & Head-Gordon, 2017) and is a strong
  general-purpose default for closed-shell organics.
- **Transition-metal chemistry** — `PBE0 EmpiricalDispersion=GD3BJ /
  def2tzvp` is reliable for ligand binding and reaction energies.
  TPSSh-D3 is a solid alternative for d-block ligand-dissociation
  thermochemistry.
- **Cheap baseline** — `B3LYP EmpiricalDispersion=GD3BJ / 6-31G(d)` if
  the user is reproducing older literature or computational budget is
  tight. Be honest that this is a publication minimum, not a state of
  the art default.

Ask if you don't know what kind of system it is. Don't guess.

## §3. Solvation

`--solvent <name>` turns on implicit solvation. Default model is
**SMD** (`scrf=(SMD,Solvent=...)`). SMD outperforms IEF-PCM by ~3–5
kcal/mol RMSD on aqueous solvation free energies (SAMPL benchmarks).
Override with `--solvation-model pcm` only when the user is matching
older PCM-based literature.

The solvation model and solvent must match across the SP / Opt / Freq
chain — running Opt in gas phase and Freq in solvent gives garbage
thermochem. The scripts don't enforce this; document it for the user.

## §4. Resources

`--mem` and `--nproc` are required. The skill does not auto-detect
because:

- `psutil.virtual_memory().available` reports the **node**, not the
  job allocation. On HPC under SLURM/cgroups it's wildly wrong.
- `os.cpu_count()` reports the node, with the same problem.
- Shared-queue nodes have other users; allocating "everything" is
  antisocial.

Pass `--mem 8GB --nproc 8` (or whatever your allocation says) and
let Gaussian's `%mem` / `%nprocshared` do their job. Gaussian itself
will refuse if `%mem` is bigger than `--mem` requested at job-submit
time, which is a clean failure mode.

## §5. g16 vs g09

v1.4 detects both at script start:

- `g16` on PATH → preferred (current generation).
- `g09` on PATH → used as fallback (still common at older sites).
- Neither → script aborts with an install pointer.

Override with `--gaussian-binary {g16,g09}`. Practical differences:

- **g16 default `SCF=Tight`** — single-points are tight by default;
  most g09 tutorials' explicit `SCF=Tight` is now redundant. Don't
  auto-add it on g16.
- **Some functionals renamed** between versions; if the user copies a
  g09 route line into a g16-driven script (or vice versa), Gaussian
  errors out with a clear "unknown method" message rather than
  silently miscomputing.
- cclib parses both versions for the v1.4 outputs (energies, dipoles,
  vib_freqs, thermochem, Mulliken/Löwdin/Hirshfeld charges).

## §6. cclib coverage and where it falls short

`gaussian_sp.py` and `gaussian_opt.py` use ASE alone for E/F/dipole.
`gaussian_freq.py` requires cclib because `ase.io.gaussian.
read_gaussian_out` **does not parse vibrational frequencies** —
checked in the ASE source. The `Freq` workflow has no in-house
shortcut.

cclib's main attribute set covers:

- `vibfreqs` (cm⁻¹), `vibirs`, `vibsyms` — vibrational analysis.
- `enthalpy`, `freeenergy`, `zpve`, `temperature` — thermochem.
- `homos`, `moenergies` — MO eigenvalues.
- `atomcharges` (a dict like `{"mulliken": [...], "lowdin": [...],
  "hirshfeld": [...]}`) — partial charges.

cclib **does not** expose **NPA** charges as a first-class attribute.
NPA requires Gaussian's `Pop=NPA` (which calls NBO) plus cclib's NBO
parser, which is a separate dep. v1.4 drops NPA from scope; if a user
asks for NPA, recommend running it manually via the standalone NBO
program. v3 may add the NBO parser dep.

## §7. Out of scope (v1.4)

These are not in v1.4 and are intentionally not blocking issues:

- **Transition-state searches** (`Opt=TS`, QST2/QST3) and **IRC**
  (`IRC=...`). TS needs a good Hessian guess (`CalcFC`/`ReadFC`) and
  IRC verification — neither fits the "skill writes a script, user
  runs it" pattern. Push to v3+.
- **Anharmonic frequencies** (`Freq=Anharmonic`). Expensive and needs
  careful normal-mode follow-up.
- **NBO analysis** (`Pop=NBO`) and **NPA charges**. cclib's NBO parser
  is a separate dep; v3 candidate.
- **Post-Hartree-Fock correlated methods** (CCSD, CCSD(T), MP2,
  CASSCF). Method-specific basis-set / memory / disk heuristics.
- **Excited-state methods** (TDDFT, CIS, EOM-CCSD).
- **Resource autodetection** — see §4.
- **Local-vs-queue submission** — v1.4 runs locally only. SLURM
  templates may land in v2.5+; for now the user wraps the script in
  their own queue script.

## §8. Known failure modes

- **Wrong multiplicity → silently converged-but-wrong wavefunction**
  for some open-shell systems. If energies look weird, double-check
  `--multiplicity`.
- **Solvation mismatch across chain** — SP gas phase, Opt solvated,
  Freq gas phase produces garbage thermochem. The scripts don't
  enforce consistency; surface this to the user.
- **GAUSS_SCRDIR unset** — Gaussian writes scratch to its default
  location, often `/tmp` or `/scratch` with small quotas. `check_env.py`
  flags this; tell users to set it before non-trivial runs.
- **Imaginary frequencies in `gaussian_freq.py`** — typically the
  preceding optimization wasn't tight enough. Re-optimize at
  `--convergence tight` or `verytight` and re-run.
- **g16 vs g09 route differences** — see §5. If a route line copied
  from older docs fails on g16, try removing redundant
  `SCF=Tight` first.

## §9. Troubleshooting

- **"Unknown keyword" / "Syntax error in route"** — usually a typo or
  a g09-specific keyword on g16 (or vice versa). Check the .com file
  written by ASE under `<label>.com`; route line is on the line
  starting with `#P`.
- **Job runs but cclib parse fails** — usually means Gaussian errored
  partway. Look at `<label>.log` for `Error termination`. cclib
  doesn't report what's missing; you have to read the log.
- **Out of disk** — Gaussian scratch fills up. Set `GAUSS_SCRDIR` to
  a fast, large-quota path before the run.
- **`%mem` insufficient** — Gaussian writes "Out-of-memory error in
  routine ..." to the .log. Re-run with a bigger `--mem`.
- **SCF doesn't converge** — try `SCF=(MaxCycle=200,XQC)` via
  `--extra-route`. If it still fails, the geometry is probably
  pathological.
