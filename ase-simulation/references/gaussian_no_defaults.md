# Gaussian no-defaults policy + solvation + resources

Part of the v1.4 Gaussian reference set. Companion files:
[`gaussian_method_selection.md`](gaussian_method_selection.md),
[`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md),
[`gaussian_log_parser.md`](gaussian_log_parser.md),
[`gaussian_failure_modes.md`](gaussian_failure_modes.md). Index:
[`gaussian.md`](gaussian.md).

## The no-defaults policy

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

## Solvation

`--solvent <name>` turns on implicit solvation. Default model is
**SMD** (`scrf=(SMD,Solvent=...)`). SMD outperforms IEF-PCM by ~3–5
kcal/mol RMSD on aqueous solvation free energies (SAMPL benchmarks).
Override with `--solvation-model pcm` only when the user is matching
older PCM-based literature.

The solvation model and solvent must match across the SP / Opt / Freq
chain — running Opt in gas phase and Freq in solvent gives garbage
thermochem. The scripts don't enforce this; document it for the user.

## Resources

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
