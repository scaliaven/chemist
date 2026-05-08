# Amber pipeline (v1.3)

Part of the v1.3 Amber reference set. Companion files:
[`amber_carveout.md`](amber_carveout.md),
[`amber_method_selection.md`](amber_method_selection.md),
[`amber_force_fields.md`](amber_force_fields.md),
[`amber_failure_modes.md`](amber_failure_modes.md). Index:
[`amber.md`](amber.md).

## Pipeline

The two-script pipeline is:

```bash
# Step 1: parameterize. Output: <prefix>.prmtop, <prefix>.rst7.
python scripts/parameterize_gaff2.py \
    --structure ligand.pdb \
    --net-charge 0 \
    --water tip3p \
    --buffer 12.0 \
    --output-prefix ligand --output-dir run/

# Step 2: run MD. Output: run/min.{nc,rst7,mdout}, run/heat.{...},
# run/density.{...}, run/prod.{...}.
python scripts/run_amber.py \
    --prmtop run/ligand.prmtop --rst run/ligand.rst7 \
    --protocol standard --output-dir run/

# Step 3: analyze the production trajectory.
python scripts/analyze_traj.py --trajectory run/prod.nc \
    --topology run/ligand.prmtop ...
```

`parameterize_gaff2.py` is idempotent — re-running it overwrites the
`.prmtop`/`.rst7` and intermediates. `run_amber.py` is **not**
idempotent: re-running with the same `--output-dir` overwrites the
`mdout` files but does not delete old `.nc` trajectories from
previous runs. Use a fresh `--output-dir` per run.
