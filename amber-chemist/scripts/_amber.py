"""Shared helpers for amber-chemist scripts.

Engine selection, mdin renderers, tleap factories, groupfile / temperature
ladder builders, mdout / rem.log parsers. Every script in this skill imports
from here so the subprocess plumbing is in one place.

This module is intentionally framework-free — stdlib only — so it loads on
any Python 3.8+ environment that has AmberTools on PATH.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Engine selection (plain MD vs MPI variants)
# ---------------------------------------------------------------------------

PLAIN_ENGINES = ("pmemd.cuda", "pmemd", "sander")
MPI_ENGINES = ("pmemd.cuda.MPI", "pmemd.MPI", "sander.MPI")

# Implicit Generalized Born model dispatch — shared by amber_md and amber_remd.
GB_MAP = {"off": 0, "gb1": 1, "gb2": 2, "gb5": 5, "gb7": 7, "gb8": 8}

# Prep-pipeline binaries required by amber_prep.py.
PREP_BINARIES = ("antechamber", "parmchk2", "tleap")


def require_binaries(names: Iterable[str]) -> None:
    """Hard-fail if any of `names` is missing from PATH."""
    missing = [b for b in names if shutil.which(b) is None]
    if missing:
        raise SystemExit(
            f"AmberTools binaries missing from PATH: {', '.join(missing)}\n"
            "Install AmberTools (free): https://ambermd.org/GetAmber.php\n"
            "Run scripts/check_env.py to see broader detection status."
        )


def infer_input_format(path: Path, override: Optional[str] = None) -> str:
    """Map a structure file's extension to an antechamber `-fi` format."""
    if override:
        return override
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("pdb", "mol2", "sdf", "mol", "xyz"):
        return suffix
    raise SystemExit(
        f"Cannot infer input format from extension '{path.suffix}'. "
        f"Pass --input-format explicitly (pdb, mol2, sdf, mol, xyz)."
    )


def pick_engine(preferred: Optional[str] = None, *, need_mpi: bool = False) -> str:
    """Return the first available Amber MD engine on PATH.

    `need_mpi=True` restricts the search to .MPI variants (REMD requires this).
    A user-supplied `preferred` is honored as long as it actually resolves on
    PATH; otherwise a clear SystemExit is raised so failures are loud.
    """
    candidates = MPI_ENGINES if need_mpi else PLAIN_ENGINES
    if preferred is not None:
        if shutil.which(preferred) is None:
            raise SystemExit(
                f"Requested engine '{preferred}' is not on PATH. "
                f"Drop --engine to auto-select, or fix PATH."
            )
        if need_mpi and preferred not in MPI_ENGINES:
            raise SystemExit(
                f"Requested engine '{preferred}' is not an MPI variant; "
                f"REMD needs one of: {', '.join(MPI_ENGINES)}."
            )
        return preferred
    for engine in candidates:
        if shutil.which(engine):
            return engine
    flavor = "MPI " if need_mpi else ""
    raise SystemExit(
        f"No {flavor}Amber MD engine on PATH. Need one of: "
        + ", ".join(candidates) + ". "
        "Run scripts/check_env.py for detection details."
    )


# ---------------------------------------------------------------------------
# mdin renderers — the v1.3 carve-out templates plus barostat / restraint /
# implicit-GB blocks parameterized for amber-chemist's wider scope.
# ---------------------------------------------------------------------------

def _restraint_block(mask: Optional[str], weight: float) -> str:
    if not mask:
        return ""
    return (
        f"  ntr=1, restraintmask='{mask}', restraint_wt={weight:g},\n"
    )


def _barostat_keys(barostat: str, taup: float = 2.0) -> str:
    """Return the ntp / barostat-flavor mdin lines."""
    if barostat == "off":
        return "  ntb=1, ntp=0,\n"
    if barostat == "berendsen":
        return f"  ntb=2, ntp=1, taup={taup:g},\n"
    if barostat == "monte_carlo":
        # Amber's Monte Carlo barostat: barostat=2 in pmemd>=18.
        return f"  ntb=2, ntp=1, barostat=2, taup={taup:g},\n"
    raise SystemExit(f"Unknown barostat: {barostat!r}")


def render_min(
    *,
    maxcyc: int = 10000,
    ncyc: int = 5000,
    cut: float = 10.0,
    restraint_mask: Optional[str] = None,
    restraint_weight: float = 10.0,
    implicit_gb: int = 0,
) -> str:
    rb = _restraint_block(restraint_mask, restraint_weight)
    if implicit_gb:
        box = f"  ntb=0, igb={implicit_gb}, cut=999.0,\n"
    else:
        box = f"  ntb=1, cut={cut:g},\n"
    return (
        f"Minimization ({maxcyc} cycles total: {ncyc} steepest, "
        f"{maxcyc - ncyc} CG)\n"
        "&cntrl\n"
        f"  imin=1, maxcyc={maxcyc}, ncyc={ncyc},\n"
        f"{box}"
        f"{rb}"
        "  ntpr=100, ntwx=0,\n"
        "&end\n"
    )


def render_heat(
    *,
    temp: float,
    n_steps: int,
    timestep: float = 0.002,
    cut: float = 10.0,
    gamma_ln: float = 2.0,
    write_every: int = 500,
    restraint_mask: Optional[str] = None,
    restraint_weight: float = 10.0,
    implicit_gb: int = 0,
) -> str:
    rb = _restraint_block(restraint_mask, restraint_weight)
    if implicit_gb:
        box = f"  ntb=0, ntp=0, igb={implicit_gb}, cut=999.0,\n"
    else:
        box = f"  ntb=1, ntp=0, cut={cut:g},\n"
    ps = n_steps * timestep
    return (
        f"Heating 0 -> {temp:.1f} K, {ps:.1f} ps NVT, SHAKE on H, "
        f"{timestep * 1000:.1f} fs\n"
        "&cntrl\n"
        "  imin=0, irest=0, ntx=1,\n"
        f"  nstlim={n_steps}, dt={timestep:g},\n"
        f"{box}"
        "  ntc=2, ntf=2,\n"
        f"  ntt=3, gamma_ln={gamma_ln:g}, ig=-1,\n"
        f"  tempi=0.0, temp0={temp:.1f},\n"
        "  nmropt=1,\n"
        f"{rb}"
        f"  ntpr=100, ntwx={write_every}, ntwr=1000, ioutfm=1,\n"
        "&end\n"
        f"&wt type='TEMP0', istep1=0, istep2={n_steps}, "
        f"value1=0.0, value2={temp:.1f} &end\n"
        "&wt type='END' &end\n"
    )


def render_density(
    *,
    temp: float,
    n_steps: int,
    timestep: float = 0.002,
    cut: float = 10.0,
    gamma_ln: float = 2.0,
    barostat: str = "berendsen",
    write_every: int = 500,
    restraint_mask: Optional[str] = None,
    restraint_weight: float = 10.0,
    irest: bool = True,
) -> str:
    """Density equilibration is meaningful only with explicit solvent.

    Defaults to a restart deck (irest=1, ntx=5) because density normally
    chains off heat's velocities. Pass irest=False for a standalone start
    from a velocity-less rst7, or pmemd aborts (see failure_modes.md).
    """
    rb = _restraint_block(restraint_mask, restraint_weight)
    bk = _barostat_keys(barostat)
    ps = n_steps * timestep
    ntx = "5" if irest else "1"
    irest_flag = "1" if irest else "0"
    return (
        f"Density equilibration, {ps:.1f} ps NPT at {temp:.1f} K "
        f"({barostat} barostat)\n"
        "&cntrl\n"
        f"  imin=0, irest={irest_flag}, ntx={ntx},\n"
        f"  nstlim={n_steps}, dt={timestep:g},\n"
        f"{bk}"
        f"  cut={cut:g},\n"
        "  ntc=2, ntf=2,\n"
        f"  ntt=3, gamma_ln={gamma_ln:g}, ig=-1,\n"
        f"  temp0={temp:.1f},\n"
        f"{rb}"
        f"  ntpr=100, ntwx={write_every}, ntwr=1000, ioutfm=1,\n"
        "&end\n"
    )


def render_prod(
    *,
    temp: float,
    n_steps: int,
    timestep: float = 0.002,
    cut: float = 10.0,
    gamma_ln: float = 2.0,
    barostat: str = "berendsen",
    write_every: int = 500,
    restraint_mask: Optional[str] = None,
    restraint_weight: float = 10.0,
    implicit_gb: int = 0,
    irest: bool = True,
    remd: bool = False,
    numexchg: int = 0,
) -> str:
    rb = _restraint_block(restraint_mask, restraint_weight)
    if implicit_gb:
        # GB has no PBC; barostat is ignored.
        box = f"  ntb=0, igb={implicit_gb}, cut=999.0,\n"
    else:
        box = _barostat_keys(barostat) + f"  cut={cut:g},\n"
    ps = n_steps * timestep
    ntx = "5" if irest else "1"
    irest_flag = "1" if irest else "0"
    extra = ""
    if remd:
        # T-REMD: pmemd reads temp0 per-replica and exchanges every
        # nstlim*1 attempts; numexchg drives the outer loop.
        extra = f"  numexchg={numexchg},\n"
    label = "REMD production" if remd else "Production MD"
    return (
        f"{label}, {ps:.1f} ps at {temp:.1f} K\n"
        "&cntrl\n"
        f"  imin=0, irest={irest_flag}, ntx={ntx},\n"
        f"  nstlim={n_steps}, dt={timestep:g},\n"
        f"{box}"
        "  ntc=2, ntf=2,\n"
        f"  ntt=3, gamma_ln={gamma_ln:g}, ig=-1,\n"
        f"  temp0={temp:.1f},\n"
        f"{extra}"
        f"{rb}"
        f"  ntpr=500, ntwx={write_every}, ntwr=10000, ioutfm=1,\n"
        "&end\n"
    )


# ---------------------------------------------------------------------------
# tleap deck factory
# ---------------------------------------------------------------------------

WATER_LEAPRC = {
    "tip3p": ("leaprc.water.tip3p", "TIP3PBOX"),
    "opc":   ("leaprc.water.opc",   "OPCBOX"),
    "spce":  ("leaprc.water.spce",  "SPCBOX"),
    "tip4pew": ("leaprc.water.tip4pew", "TIP4PEWBOX"),
}


def write_tleap_deck(
    path: Path,
    *,
    prefix: str,
    mol2: Path,
    frcmod: Path,
    water: str,
    buffer_a: float,
    neutralize: bool,
    salt_conc: float = 0.0,
    box_shape: str = "rect",
    implicit: bool = False,
) -> None:
    """Render a tleap input deck.

    `implicit=True` skips solvateBox / addions entirely — the prmtop is
    written for vacuum / implicit-solvent MD. Box-shape `oct` uses
    `solvateOct` which produces a truncated octahedron (smaller waterbox).
    """
    lines = ["source leaprc.gaff2"]
    if not implicit:
        if water not in WATER_LEAPRC:
            raise SystemExit(
                f"Unknown water model {water!r}; supported: "
                + ", ".join(WATER_LEAPRC)
            )
        leaprc_water, solvent_box = WATER_LEAPRC[water]
        lines.append(f"source {leaprc_water}")
    lines += [
        f"LIG = loadmol2 {mol2.name}",
        f"loadamberparams {frcmod.name}",
    ]
    if not implicit:
        solvate_cmd = "solvateOct" if box_shape == "oct" else "solvateBox"
        lines.append(f"{solvate_cmd} LIG {solvent_box} {buffer_a:.2f}")
        if neutralize:
            lines += [
                "addions LIG Na+ 0",
                "addions LIG Cl- 0",
            ]
        if salt_conc > 0.0:
            # `addionsrand` adds a roughly correct ion count; tleap accepts
            # a molarity-ish argument as integer counts only, so we estimate
            # via the box volume the user implicitly chose.
            n_ions = max(1, int(round(salt_conc * 100)))
            lines += [
                f"addionsrand LIG Na+ {n_ions} Cl- {n_ions}",
            ]
    lines += [
        f"saveAmberParm LIG {prefix}.prmtop {prefix}.rst7",
        f"savePdb LIG {prefix}_solvated.pdb",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# REMD: temperature ladder + groupfile builder
# ---------------------------------------------------------------------------

def build_temperature_ladder(
    n_replicas: int,
    *,
    t_low: float = 300.0,
    t_high: float = 400.0,
    ladder: str = "geometric",
    explicit: Optional[Iterable[float]] = None,
) -> list[float]:
    """Return a list of temperatures for the requested ladder shape.

    `geometric` uses T_i = T_low * (T_high/T_low)^(i/(N-1)). It's the
    standard approximation when the heat capacity is roughly constant
    across the range — fine for small organics in water, less great for
    large biomolecules where vdSpoel solvers are preferred.
    """
    if ladder == "explicit":
        if not explicit:
            raise SystemExit(
                "ladder=explicit requires --temps to be set."
            )
        temps = [float(t) for t in explicit]
        if len(temps) != n_replicas:
            raise SystemExit(
                f"--n-replicas={n_replicas} but --temps lists {len(temps)} "
                "values."
            )
        return temps
    if ladder == "vdspoel":
        # v1.0 falls back to geometric and prints a warning at the call
        # site (see amber_remd.py). The full Patriksson-van der Spoel
        # iterative solver is a v1.1 candidate.
        ladder = "geometric"
    if ladder == "geometric":
        if n_replicas < 2:
            raise SystemExit("--n-replicas must be >= 2 for REMD.")
        ratio = t_high / t_low
        return [t_low * ratio ** (i / (n_replicas - 1)) for i in range(n_replicas)]
    raise SystemExit(f"Unknown ladder shape: {ladder!r}")


def write_groupfile(
    path: Path,
    *,
    n_replicas: int,
    base_dir: Path,
    mdin_name: str = "prod.in",
    rst_name: str = "prod.rst7",
    out_rst_name: str = "prod.rst7",
    out_mdout: str = "prod.mdout",
    out_nc: str = "prod.nc",
    initial_rst: Optional[Path] = None,
) -> None:
    """Write a pmemd groupfile with one line per replica.

    Each replica lives in `base_dir/replica_NN/`; the input rst7 is the
    same `initial_rst` for replica 0 and per-replica heat-and-density
    outputs for the rest in single-rst mode (caller's choice).
    """
    lines: list[str] = []
    for i in range(n_replicas):
        rep_dir = base_dir / f"replica_{i:02d}"
        rep_dir.mkdir(parents=True, exist_ok=True)
        crd = initial_rst if initial_rst is not None else rep_dir / rst_name
        lines.append(
            f"-O -i {rep_dir}/{mdin_name} "
            f"-o {rep_dir}/{out_mdout} "
            f"-c {crd} "
            f"-r {rep_dir}/{out_rst_name} "
            f"-x {rep_dir}/{out_nc}"
        )
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Output parsers — mdout (energy summary) + rem.log (exchange acceptance)
# ---------------------------------------------------------------------------

_MDOUT_SCALAR_RE = re.compile(
    r"\s*([A-Za-z0-9_+\-]+)\s*=\s*([-+0-9.Ee]+)"
)


def parse_mdout(mdout: Path) -> dict:
    """Extract the last NSTEP block's scalar energies from a pmemd mdout.

    Returns a dict with at least: TIME, TEMP, ETOT, EPTOT, EKTOT, BOND,
    ANGLE, DIHED, VDWAALS, EEL, EHBOND, RESTRAINT, EKCMT, VIRIAL, VOLUME,
    DENSITY (whichever appear in the file). Missing keys are omitted —
    implicit-solvent runs lack VOLUME/DENSITY etc.
    """
    text = mdout.read_text(errors="replace")
    # The "AVERAGES OVER ..." or last "NSTEP =" block has the canonical
    # final-frame numbers. We grab everything from the last "NSTEP =" up
    # to the next blank line that is followed by a new section header.
    nstep_blocks = list(re.finditer(r"^\s*NSTEP\s*=.*$", text, re.MULTILINE))
    if not nstep_blocks:
        return {}
    last = nstep_blocks[-1]
    # Take the next ~30 lines as the energy block.
    tail = text[last.start():last.start() + 4000]
    out: dict = {}
    for line in tail.splitlines():
        if line.strip().startswith("---"):
            break
        for m in _MDOUT_SCALAR_RE.finditer(line):
            key = m.group(1).upper()
            try:
                out[key] = float(m.group(2))
            except ValueError:
                pass
    return out


def mdout_succeeded(mdout: Path) -> bool:
    """Heuristic: pmemd writes 'Total wall time' to mdout on clean exit.

    Production mdout files can be tens of MB on long runs; we only need
    the closing banner, so tail-read the last 4 KB.
    """
    if not mdout.exists():
        return False
    try:
        with mdout.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    return "Total wall time" in tail


_REMLOG_PAIR_RE = re.compile(
    r"Replica\s+(\d+)\s*<->?\s*(\d+).*?attempts\s*=\s*(\d+).*?accepts?\s*=\s*(\d+)"
)


def parse_remlog(remlog: Path) -> list[dict]:
    """Return a list of {pair, i, j, attempts, accepts, rate} dicts.

    pmemd's rem.log format isn't as locked down as mdout, so this is a
    best-effort regex over the most common AmberTools25 layout. If the
    regex finds nothing, the caller should print a warning rather than
    pretending to have data.
    """
    if not remlog.exists():
        return []
    text = remlog.read_text(errors="replace")
    rows: list[dict] = []
    for m in _REMLOG_PAIR_RE.finditer(text):
        i, j, att, acc = int(m[1]), int(m[2]), int(m[3]), int(m[4])
        rate = (acc / att * 100.0) if att else 0.0
        rows.append({"i": i, "j": j, "attempts": att,
                     "accepts": acc, "rate": rate})
    return rows


# ---------------------------------------------------------------------------
# Subprocess wrapper with predictable error reporting
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    stdout_to: Optional[Path] = None,
    check: bool = True,
    dry_run: bool = False,
) -> int:
    """Run `cmd`, print it first, optionally redirect stdout to a file.

    `dry_run=True` prints the command and skips execution. Returns the
    process return code (0 on dry-run).
    """
    print("$ " + " ".join(cmd))
    if dry_run:
        return 0
    if stdout_to is not None:
        with stdout_to.open("w") as fh:
            rc = subprocess.run(cmd, cwd=cwd, stdout=fh,
                                stderr=subprocess.STDOUT).returncode
    else:
        rc = subprocess.run(cmd, cwd=cwd).returncode
    if check and rc != 0:
        raise SystemExit(
            f"Command failed (rc={rc}): {' '.join(cmd)}"
            + (f"\nInspect {stdout_to}." if stdout_to else "")
        )
    return rc


def parse_time_to_steps(value: str, timestep_ps: float) -> int:
    """Convert a CLI time string to step count.

    Accepts `"5ns"`, `"500ps"`, `"100000fs"`, or a bare integer (steps).
    Bare integer is allowed but flagged so users don't conflate steps
    with picoseconds.
    """
    s = value.strip().lower()
    for unit, ps_per_unit in (("ns", 1000.0), ("ps", 1.0), ("fs", 0.001)):
        if s.endswith(unit):
            qty = float(s[: -len(unit)])
            ps = qty * ps_per_unit
            return max(1, int(round(ps / timestep_ps)))
    # Bare integer = steps.
    try:
        n = int(s)
    except ValueError:
        raise SystemExit(
            f"Cannot parse --time={value!r}. Use suffixes like '1ns', "
            "'500ps', '100000fs', or a bare integer step count."
        )
    print(f"[amber] WARNING: --time={value} is being treated as a raw step "
          "count. Use unit suffixes (ns/ps/fs) to be explicit.")
    return n
