---
name: ase-chemist
description: Use this skill whenever the user wants to run, set up, or analyze atomistic simulations on molecules or materials. This covers: molecular dynamics (MD, NVE, NVT, NPT, Langevin, Nose-Hoover) including thermalization, equilibration, and "warm up the system" requests; geometry optimization, energy minimization, or relaxation (BFGS, FIRE, LBFGS — "minimize this molecule", "relax this structure", "find the equilibrium geometry"); vibrational frequency, normal-mode, Hessian, and zero-point-energy analysis; NEB minimum-energy-path scaffolding (inline; no turnkey transition-state search); structure building (small molecules, bulk crystals, surfaces like fcc111, slabs with adsorbates); trajectory analysis (RMSD, RMSF, RDF, energy drift); single-point energy and force evaluation; binding, interaction, and adsorption energy calculations; explicit-solvent small-molecule MD with GAFF2 + AM1-BCC charges via antechamber, parmchk2, tleap, and pmemd; DFT via Gaussian (g16/g09) — SP / Opt / Freq / thermochemistry (ZPE, enthalpy, Gibbs free energy) — with B3LYP, ωB97X-D, M06-2X, PBE0 functionals, def2-TZVP / 6-31G(d) basis sets, and SMD/PCM solvation; foundation-model ML potentials (MACE-MP-0, MACE-OFF); semi-empirical xTB (GFN1-xTB, GFN2-xTB via tblite); ASE built-ins (EMT, Lennard-Jones, TIP3P); and electronic observables (HOMO-LUMO gap, dipole, Mulliken charges). Reach for this skill even when the user does not name ASE — phrases like "minimize this molecule", "relax this geometry", "thermalize at 300 K", "equilibrate the system", "compute the binding energy", "run MD on water", "build a Pt(111) slab", "compute frequencies", "speed up this MD with a foundation model", "use MACE", "run a 5000-atom system", "ligand MD in water", "GAFF2 parameterization", "AM1-BCC charges", "antechamber", "run a DFT calculation", "compute thermochemistry at B3LYP/def2-TZVP", "Gibbs free energy of this reaction", "Gaussian SMD water", or "DFT frequency analysis" should all trigger this skill. For Amber-deep prompts (REMD, MMPBSA, cpptraj, esander, alanine scan, GB-implicit MD, ff19SB, OL21, per-residue decomposition), route to the sibling `amber-chemist` skill instead.
license: MIT
---

# ASE Simulation Skill (v1.4)

## Always do this first

Before any non-trivial task, run:

```bash
python scripts/check_env.py
```

It prints which calculators and analysis tools are actually installed, and
ends with a one-line "what you can run right now" summary. **Recommend a
method that the environment supports** — do not ask the user to install xTB if
EMT or LJ already covers the question.

If a backend is missing and the user wants it, prefer the conda install on
HPC / conda systems:

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib
```

…and pip only when conda isn't available:

```bash
pip install ase tblite mdanalysis matplotlib
```

For MACE foundation-model support (v1.2+), install separately:

```bash
pip install mace-torch
```

`tblite` ships GFN1-xTB and GFN2-xTB and is the supported successor to the
deprecated `xtb-python`. If `check_env.py` reports `[BROKEN] tblite ...
C extension unloadable`, the pip wheel is libgfortran-incompatible — switch
to `conda install -c conda-forge tblite-python`. The standalone `xtb`
binary (Grimme group) adds GFN0 and GFN-FF if it's on PATH.

`mace-torch` provides the **MACE-MP-0** and **MACE-OFF** calculators
(element-set routing and the ~1k-atom size cliff are covered in Step-2
rule 6). MACE requires `torch`; CUDA is strongly recommended (CPU mode
is ~10× slower). `check_env.py` reports CUDA status and a size-cliff warning.

## Method selection

Walk these three steps in order. Each rule names *what* to do and *why*; if
the user's case doesn't fit the "because", the rule probably doesn't apply
and you should keep walking.

### Step 1 — what task is this?

| Task | Tool | Notes |
|---|---|---|
| Optimize / minimize / relax | `scripts/optimize.py` | FIRE for far-from-equilibrium, BFGS otherwise |
| MD at temperature T | `scripts/run_md.py` | Langevin NVT is the default ensemble |
| Production explicit-solvent MD on a small organic | `scripts/parameterize_gaff2.py` then `scripts/run_amber.py` | GAFF2 + AM1-BCC, TIP3P/OPC water, min/heat/density/prod via pmemd. See `references/amber.md` |
| **DFT single-point** (energy / forces / dipole / charges at DFT level) | `scripts/gaussian_sp.py` | wraps `ase.calculators.gaussian.Gaussian`; in-house parser for charges/MO. **No method/basis defaults — refuse without `--method`/`--basis`/`--charge`/`--mult`/`--mem`/`--nproc`.** |
| **DFT geometry optimization** | `scripts/gaussian_opt.py` | uses `GaussianOptimizer` (Gaussian L103 — much faster than ASE-BFGS-around-Gaussian-SP). `--convergence tight` for Freq input. |
| **DFT frequency + thermochemistry** | `scripts/gaussian_freq.py` | Freq job parsed by in-house `_gaussian_log.py` helper (no cclib). Tighten the optimization first. |
| Vibrations / Hessian / ZPE (xTB-level) | `ase.vibrations.Vibrations` inline | Optimize to fmax ≤ 0.01 first, or you get spurious imaginary modes |
| HOMO-LUMO / dipole / charges | `scripts/single_point.py` (with `--calculator xtb`) | Returns gap, dipole, Mulliken charges, bond orders. **HOMO-LUMO is the raw eigenvalue gap — see `references/xtb.md` for the convention.** For DFT-level HOMO/LUMO, use `gaussian_sp.py`. |
| Binding / interaction / adsorption energy | three runs of `scripts/single_point.py` (or `gaussian_sp.py` for DFT) | E(complex) − E(A) − E(B); use the same calculator for all three |
| Transition state / barrier | NEB inline (see `references/ase_core.md`) | No turnkey script in v1 |
| Build a structure | `ase.build` inline | molecule / bulk / fcc111 / add_adsorbate |
| Analyze a trajectory | `scripts/analyze_traj.py` | RMSD / RMSF / energy drift / optional RDF |

### Step 2 — pick the calculator

Apply the first rule that fits the system, in this order:

1. **If the user explicitly named a calculator** (xTB, EMT, GFN2, TIP3P,
   …), use that one. *Why:* don't second-guess an explicit choice.
2. **If the system contains only EMT-supported metals** (Al, Cu, Ag, Au,
   Ni, Pd, Pt, plus H/C/N/O as adsorbates), prefer **EMT**. *Why:* it's
   free, instant, and the user probably wants a quick metallic-system
   answer.
3. **If the system is pure water** (H₂O molecules only), the choice
   depends on the task:
   - **Production MD** → **TIP3P**. *Why:* parameterized for exactly this
     case. **Requires `ase.constraints.FixBondLengths`** (rigid-body
     model; bare ASE lets the O–H/H–H bonds vibrate and the run blows
     up). The bundled scripts do **not** auto-attach it — add it inline.
     See `references/ase_core.md` §Water (TIP3P + FixBondLengths).
   - **One-off relaxations or quick energy / single-point checks** on
     small water systems → **GFN2-xTB**. *Why:* simpler — no constraints
     to set up — and small water clusters are well within xTB's accuracy
     range. `scripts/optimize.py` and `scripts/single_point.py` work as
     expected with `--calculator xtb`.
4. **If the system has organic / main-group chemistry** (heteroatoms,
   non-EMT elements, organic functional groups, ionic bonding), use
   **tblite GFN2-xTB**. *Why:* EMT will silently give nonsense for
   non-metals; GFN2-xTB is the cheapest method that knows real chemistry.
   *Sub-rule: if the user wants production-length explicit-solvent MD
   (≥ 100 ps in a TIP3P/OPC box) on a single small organic, switch to
   **GAFF2 + AM1-BCC** via `scripts/parameterize_gaff2.py` →
   `scripts/run_amber.py`. xTB MD with explicit solvent past ~100 ps
   is impractical (the box pushes well past 1k atoms once water is
   added); GAFF2 is the right tool for that task and the v1.3 scripts
   handle the antechamber → tleap → pmemd pipeline. See
   `references/amber.md` for force-field and water-model details.*

   > **⚠️ Architecture note (v1.3 Amber).** Amber is the **only engine in
   > the skill that does not run through ASE** — `parameterize_gaff2.py`
   > and `run_amber.py` shell out to AmberTools and pmemd, and the MD loop
   > runs natively in pmemd. This is a performance choice, not forced: ASE
   > exposes a CPU-only in-process path (`ase.calculators.amber.SANDER`),
   > but pmemd.cuda is ~10–50× faster on production-sized systems. The
   > trade is under review (four options open). See `references/amber.md`
   > §1 and `PLAN.md` §"Phase 3", and surface the carve-out when
   > recommending GAFF2 so the user can decide whether they want it.
5. **If the system is a transition-metal complex and GFN2 fails to
   converge**, fall back to **GFN1-xTB**. *Why:* GFN1 is more robust on
   d-block elements at the cost of some accuracy.
6. **If the system is past the xTB size cliff (~1k atoms; xTB MD on a
   system that size is impractical past a few ps), reach for a MACE
   foundation model.** *Why:* GFN2-xTB MD
   stops being practical at ~1k atoms; MACE foundation models (MACE-OFF
   for organics, MACE-MP-0 for crystals/materials) deliver roughly
   DFT-quality energies and forces in that 1k–~2k atom range on a
   40 GB GPU. Use `--calculator mace` in `optimize.py` /
   `run_md.py`; routing is automatic by element set.
   **Cross-validation against GFN2-xTB is on by default for MD** —
   every 1 ps the script recomputes E and F on the latest frame
   through xTB and aborts the run when MAE_F > 100 meV/Å. This is
   the contract under which MACE is recommended at all; do not turn
   it off (`--no-validate`) without a specific reason. Read
   `references/ml_potentials.md` for the full method-selection rules
   and known failure modes (liquid mixtures, OOD geometries).
7. **If the system is past the MACE ceiling too** (>2k atoms on a
   40 GB GPU, >~1k on CPU, or anything past ~50k atoms in v1), say
   so out loud: "v1.2 caps at MACE-medium on a single GPU; v2.2 is
   slated to add larger ML potentials (CHGNet, Orb) and v2.3 adds
   Amber for biomolecular MD beyond GAFF2 small molecules." See
   `references/ase_core.md` §Appendix for the full size table.
8. **If the user explicitly wants DFT** (B3LYP, ωB97X-D, M06-2X,
   PBE0, post-HF, "publication thermochem", "transition-metal
   barriers within 1 kcal/mol", or "compute G298") and Gaussian is
   available — use **`gaussian_sp.py` / `gaussian_opt.py` /
   `gaussian_freq.py`**. *Why:* xTB tops out at ~few-kcal/mol error
   on relative energies and is unreliable on transition metals;
   DFT is the right tool. **No method/basis defaults** — surface a
   recommendation (ωB97X-D/def2-TZVP for organics; PBE0-D3(BJ)/def2-
   TZVP for transition metals; see `references/gaussian.md` §1) and
   confirm before running. The scripts also require explicit
   `--charge`, `--mult`, `--mem`, `--nproc`. Solvent → SMD by
   default. Thermochem parsing is in-house (`_gaussian_log.py`),
   no cclib dependency.

### Step 3 — confirm the calculator is installed

Read the `[OK]` / `[MISSING]` lines from `scripts/check_env.py`. If your
chosen calculator is `[MISSING]`, ask the user to install it; **do not
silently substitute a wrong-physics fallback**. EMT on an organic is the
classic failure mode — it will return numbers that look fine and are
meaningless.

## Verification & clarification

### Don't ask what's already named — and frame what you do ask

The two failure modes to avoid: silently picking wrong physics (EMT
on an organic returns plausible nonsense; 2 fs timestep without
hydrogen constraints; MACE-OFF on a system with metals; Gaussian
DFT without explicit method/basis), and re-asking the user something
the prompt or structure file already names.

When the answer is genuinely underdetermined, frame the question
with the option you'd pick and the reason — e.g., *"GFN2-xTB looks
right here because the system has heteroatoms; want me to fall back
to GFN1 for d-block robustness instead?"* — beats a blank "which
method?".

### Ask the user to verify before recommending execution

After choosing parameters, restate them in a short block and ask the
user to confirm before suggesting they run anything. The minimum to
surface:

- Calculator (and GFN level if applicable)
- Optimizer / ensemble
- For MD: temperature, friction, timestep, n_steps
- For optimization: fmax, max_steps
- Output paths that will be written

Keep it tight — a 4-6 line summary, not a paragraph. If the user has
already approved the plan, don't re-ask.

## Scripts — when to invoke each

All scripts live in `scripts/` and are parameterized via argparse.
Run with `--help` to see options.

**Default: call the bundled CLI.** Write inline only for a *specific,
named* capability the script lacks (e.g., "run_md.py has no `--barostat`,
user asked for NPT") — confirmable via `--help`. Not justifications:
user phrasing ("write me a script" — the CLI one-liner IS a script),
readability or pedagogy (point at `scripts/<name>.py` instead), or
tweaks already covered by flags (fmax, timestep, ensemble, calculator,
seed). If the gap is a missing flag, prefer adding the flag over a
one-off rewrite. Name the gap in one sentence before any inline code —
no sentence, no carve-out.

Per-script use:

- **`scripts/check_env.py`** — Reports installed backends and a
  one-line capability summary. Run first on any non-trivial task so you
  recommend a method the environment actually supports.
- **`scripts/optimize.py`** — Geometry optimization with BFGS / FIRE /
  LBFGS, calculator EMT / LJ / TIP3P / xTB / MACE. Real-gas LJ via
  `--epsilon`/`--sigma`/`--rc`. MACE via `--calculator mace`
  (auto-routed to MACE-OFF for pure organics, MACE-MP-0 otherwise).
- **`scripts/run_md.py`** — NVE / NVT-Langevin / NVT-Nose-Hoover MD with
  EMT / LJ / TIP3P / xTB / MACE. Defaults tuned for organic molecules
  (1 fs, 300 K, Langevin friction 0.01/fs, log every 100 steps). With
  `--calculator mace`, GFN2-xTB cross-validation runs by default (the
  contract in Step-2 rule 6; flags `--validate-every`, `--abort-mae-f`,
  `--no-validate`).
- **`scripts/ml_calculator.py`** — Helper exposing
  `make_ml_calc(atoms, system_class=, device=, model_size=)`. Imported
  by `optimize.py` and `run_md.py` when `--calculator mace`. Run as
  `python scripts/ml_calculator.py --structure mol.xyz` to print
  routing without loading weights.
- **`scripts/validate_ml_md.py`** — Post-hoc cross-validation of a saved
  MACE trajectory against GFN2-xTB. Same MAE_F threshold as `run_md.py`
  runtime validation; writes `validation.csv`. For trajectories
  produced with `--no-validate` or to re-validate with a different
  reference / stride.
- **`scripts/parameterize_gaff2.py`** — Drives `antechamber -c bcc`
  (AM1-BCC) → `parmchk2` (frcmod) → `tleap` (solvate in TIP3P/OPC,
  neutralize with Na+/Cl-) for a small organic. Output: `.prmtop` /
  `.rst7` pair for `run_amber.py`. **Mandatory: `--net-charge` matches
  the formal charge** — getting it wrong silently shifts every partial
  charge.
- **`scripts/run_amber.py`** — Runs Amber MD on a `.prmtop` (`--prmtop`)
  / `.rst7` (`--rst`, not `--rst7`) pair. `--protocol standard` runs
  min → heat (50 ps NVT, 0→300 K) → density (100 ps NPT) → prod (default
  500 ps NPT). Engine auto-picks `pmemd.cuda` > `pmemd` > `sander`
  (`--engine`). Outputs NetCDF `.nc`. v1.3 `mdin` defaults are
  GAFF2-tuned (protein/NA prmtops run but may want different
  cutoffs/restraints). For Amber-deep workflows (REMD, MMPBSA,
  restart/extend, implicit-GB), use `amber-chemist` instead.
- **`scripts/gaussian_sp.py`** — DFT single-point E/F/dipole via
  `ase.calculators.gaussian.Gaussian` (g09 fallback). Mulliken charges
  and HOMO/LUMO parsed by `_gaussian_log.py`. Required flags + SMD
  default per Step-2 rule 8 — no silent defaults.
- **`scripts/gaussian_opt.py`** — DFT geometry optimization via
  `GaussianOptimizer` (Gaussian's L103, one g16/g09 invocation).
  `--convergence` is a string (`loose`/`default`/`tight`/`verytight`),
  not a numeric eV/Å. Use `tight` or `verytight` if the optimized
  geometry feeds into a Freq job.
- **`scripts/gaussian_freq.py`** — DFT frequency + thermochemistry
  (vib_freqs / ZPE / enthalpy / Gibbs G) via `_gaussian_log.py`. Reports
  imaginary modes (warning + nonzero exit). **Freq method/basis must
  match the optimization** — not enforced; surface it.
- **`scripts/_gaussian_log.py`** — Helper module: regex parsers for
  Gaussian .log fields ASE doesn't cover (vib_freqs, thermochem,
  Mulliken charges, MO eigenvalues). Imported by gaussian_sp.py and
  gaussian_freq.py. Stdlib-only.
- **`scripts/single_point.py`** — Single-point energy plus xTB
  electronic observables (dipole, Mulliken charges, Wiberg bond
  orders, HOMO-LUMO raw eigenvalue gap). Tagged `key=value` output.
  Optimize first — single-point observables on a strained geometry are
  nonsense. For binding-energy decomposition, run three times.
- **`scripts/analyze_traj.py`** — RMSD, RMSF, energy drift, optional
  RDF from a trajectory. Saves PNG plots and CSV data alongside the
  input. **These analyses ARE the script's primary purpose — do not
  write a substitute for any of them inline.** Handles edge cases
  (Kabsch alignment, missing-calculator fallback for energy drift,
  periodic unwrapping for RDF) that an inline rewrite will get wrong.

### Growing the skill: when to offer to bundle new scripts

When inline code looks like recurring work, offer to promote it to a
bundled script. **Offer only when all hold:** the code is substantial
(>~30 lines or a parametric workflow), no existing `scripts/` entry
covers it, and the request reads as recurring ("for each molecule",
"every time I get a new structure"). Don't offer for trivial one-shots,
already-covered tasks, or exploratory/definitional questions.

If the user says yes: refactor into `scripts/<verb>.py` (naming like
`optimize.py` / `run_md.py`) with argparse + a top-of-file docstring
saying *when* to reach for it, match output conventions (banner, tagged
`[OK]` / `[INFO]` lines, plots/CSVs alongside input, meaningful exit
codes), add a one-line SKILL.md §Scripts bullet, and verify with
`--help` + one example. If no, leave it and don't re-ask this session.

## References — read these on demand

Each file is short and topic-scoped; read the one whose topic comes up.

- **`references/ase_core.md`** — structure I/O, `ase.build`, optimizers, MD integrators, units, Trajectory format, NEB scaffolding.
- **`references/xtb.md`** — tblite install, GFN1 vs GFN2, the standalone `xtb` binary (GFN0/GFN-FF), xTB observables, limitations.
- **`references/analysis.md`** — ASE readers vs MDAnalysis, recipes for the `analyze_traj.py` analyses, pitfalls.
- **`references/ml_potentials.md`** — MACE vs xTB, the cross-validation contract, MACE failure modes, the GPU ceiling, troubleshooting.
- **`references/amber.md`** — when GAFF2 wins, the antechamber→parmchk2→tleap→pmemd pipeline, force-field/water choices, engine selection, failure modes. Protein/NA (ff19SB/OL21) deferred to v2.3.
- **`references/gaussian.md`** — when Gaussian beats xTB, the no-defaults policy + recommended method/basis, SMD vs PCM, g16/g09, the `_gaussian_log.py` parser, failure modes. Opt=TS/IRC/NBO/TDDFT/post-HF deferred to v3+.

**Smell test — don't fabricate technical semantics.** If you are
about to write *"I think `<keyword>` defaults to ..."* or *"the
standard value for `<flag>` is roughly ..."* — for a Gaussian route
line, an xTB GFN convention, a MACE element-set rule, an Amber mdin
keyword, or any other domain-specific knob — stop and check the
right reference file (or its upstream manual). Hallucinated semantics
is a high-cost, hard-to-detect failure mode because the calculation
often *runs* with the wrong value and produces plausible-looking
output.

## Defaults and conventions

- **Units**: ASE uses eV, Å, ASE-time-units. Use `ase.units.fs` /
  `ase.units.kB` rather than raw numbers. Temperature kwarg is
  `temperature_K=` (canonical since ASE 3.21.0).
- **Timestep**: 1 fs is safe for organic molecules with all-atom dynamics.
  Bump to 2 fs only if you constrain hydrogen bonds (ASE doesn't do
  RATTLE/SHAKE elegantly, so 1 fs is the safer default).
- **Friction (Langevin)**: 0.01 / fs is a reasonable thermostat coupling
  for production. Higher values (0.1 / fs) for fast equilibration.
- **Nose-Hoover coupling**: `--tdamp 100 fs` is the default characteristic
  timescale for the deterministic `nvt-nose-hoover` thermostat in `run_md.py`.
- **Optimization tolerance**: `fmax=0.05 eV/Å` for production geometries;
  `0.01 eV/Å` for vibrational analysis input.
- **Trajectory format**: prefer `.traj` (ASE binary, includes calculator
  results) over `.xyz` (positions only) when energies/forces matter
  downstream.
- **Random seed**: Set `seed` in MD integrators if reproducibility matters
  to the user.

## Reporting results

When you finish a task, report:
1. The method used (calculator + integrator/optimizer) and **why** it was
   chosen given system size, available backends, and accuracy needed.
2. Final numbers (energy, fmax, temperature, etc.) with units.
3. Where outputs were written (trajectory, plots, CSVs).
4. Any caveats (e.g., "GFN2-xTB; transition-metal accuracy is limited",
   "NVE energy drift was 0.3 meV/atom over 1 ps — reasonable").

## What v1 does NOT support

Be honest about scope. Deferrals:
- Biopolymer Amber MD (ff19SB+OPC / OL21) → v2.3. BYO-prmtop runs work
  with `run_amber.py` but `mdin` defaults are GAFF2-tuned — flag the
  mismatch.
- Gaussian `Opt=TS` / QST / IRC, anharmonic Freq, NBO/NPA, post-HF
  (CCSD/MP2/CASSCF), excited states (TDDFT/CIS/EOM-CCSD) → v3+; see
  `references/gaussian.md` §7. (Method strings pass to Gaussian
  verbatim, so a post-HF route *runs*, but gets no method-specific
  parsing or validation — prefer DFT.)
- ML potentials beyond MACE (CHGNet, Orb-v3, M3GNet, SevenNet) →
  v2.2+; MACE-MP-0 covers most of the same scope today (see
  `references/ml_potentials.md`).
- VASP, Quantum ESPRESSO → no v2 plan; CP2K / FHI-aims bridges may
  land in v3.
- Free-energy (TI/FEP/MBAR), enhanced sampling (REMD, metadynamics,
  umbrella), QM/MM, constant-pH.
- RESP charges via Gaussian — AM1-BCC only in v1.3.
- SLURM submission scripts; web GUI / visualization servers.
