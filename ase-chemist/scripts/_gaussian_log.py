"""In-house parser for Gaussian .log files.

ASE's read_gaussian_out (in ase.io.gaussian) handles energy / forces /
dipole, but does **not** parse vibrational frequencies, thermochem,
Mulliken charges, or MO eigenvalues. This module fills those gaps
without taking a cclib dependency, so the v1.4 Gaussian path stays
"everything through ASE-or-our-own-code" — same shape as MACE / xTB.

The parsers are regex-based and target Gaussian 09 / 16 output, which
has been format-stable through both versions. If a parser misses a
field on an unusual log it fails silently (returns empty dict / None)
rather than raising — callers should check the return value.

Public API:
    parse_thermochem(log_path)       -> dict   (vib_freqs, ZPE, H, G, ...)
    parse_mulliken_charges(log_path) -> list[float] | None
    parse_homo_lumo(log_path)        -> (HOMO_eV, LUMO_eV) | None
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


HARTREE_EV = 27.211386245988


def parse_thermochem(log_path: Path | str) -> dict:
    """Extract vibrational frequencies and thermochemistry from a
    Gaussian Freq job's .log.

    Returns a dict with the following keys (any may be absent if
    Gaussian didn't print the corresponding line):

        vib_freqs              list[float], cm^-1, signed (negative = imaginary)
        n_imag                 int
        zpe_eV                 zero-point energy (eV)
        enthalpy_eV            sum of electronic + thermal enthalpy (eV)
        gibbs_eV               sum of electronic + thermal free energy (eV)
        thermal_E_eV           sum of electronic + thermal energies (eV)
        temperature_K          thermochem temperature

    Returns an empty dict if no Freq output was found.
    """
    text = Path(log_path).read_text()
    out: dict = {}

    # Vibrational frequencies. Gaussian prints these in groups of three
    # on " Frequencies --" lines.
    freqs: list[float] = []
    for m in re.finditer(r" Frequencies --\s+(.+)", text):
        freqs.extend(float(x) for x in m.group(1).split())
    if freqs:
        out["vib_freqs"] = freqs
        out["n_imag"] = sum(1 for f in freqs if f < 0)

    # ZPE / thermal corrections / sums (all in Hartree in the log).
    patterns = {
        "_zpe_corr_h":    r"Zero-point correction=\s+([-\d.]+)",
        "_thermal_e_h":   r"Thermal correction to Energy=\s+([-\d.]+)",
        "_thermal_h_h":   r"Thermal correction to Enthalpy=\s+([-\d.]+)",
        "_thermal_g_h":   r"Thermal correction to Gibbs Free Energy=\s+([-\d.]+)",
        "_sum_e_zpe_h":   r"Sum of electronic and zero-point Energies=\s+([-\d.]+)",
        "_sum_e_therm_h": r"Sum of electronic and thermal Energies=\s+([-\d.]+)",
        "_sum_e_h_h":     r"Sum of electronic and thermal Enthalpies=\s+([-\d.]+)",
        "_sum_e_g_h":     r"Sum of electronic and thermal Free Energies=\s+([-\d.]+)",
    }
    raw: dict = {}
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            raw[key] = float(m.group(1))

    # User-facing eV-converted values
    if "_zpe_corr_h" in raw:
        out["zpe_eV"] = raw["_zpe_corr_h"] * HARTREE_EV
    if "_sum_e_h_h" in raw:
        out["enthalpy_eV"] = raw["_sum_e_h_h"] * HARTREE_EV
    if "_sum_e_g_h" in raw:
        out["gibbs_eV"] = raw["_sum_e_g_h"] * HARTREE_EV
    if "_sum_e_therm_h" in raw:
        out["thermal_E_eV"] = raw["_sum_e_therm_h"] * HARTREE_EV

    # Temperature (Gaussian prints "Temperature  298.150  Kelvin")
    m = re.search(r"Temperature\s+([\d.]+)\s*Kelvin", text)
    if m:
        out["temperature_K"] = float(m.group(1))

    return out


def parse_mulliken_charges(log_path: Path | str) -> Optional[list[float]]:
    """Return Mulliken charges per atom from the most recent
    ' Mulliken charges:' block, or None if no block is found.
    """
    text = Path(log_path).read_text()
    # The block format is:
    #   Mulliken charges:
    #                  1
    #       1  C   -0.123456
    #       2  H    0.234567
    #       ...
    #    Sum of Mulliken charges = ...
    blocks = re.findall(
        r" Mulliken charges:\s*\n[^\n]*\n((?:[^\n]+\n)+?)\s+Sum of Mulliken",
        text,
    )
    if not blocks:
        return None
    last = blocks[-1]
    charges: list[float] = []
    for line in last.strip().splitlines():
        parts = line.split()
        # Expect "  1  C   -0.123456"; last column is the charge.
        if len(parts) >= 3:
            try:
                charges.append(float(parts[-1]))
            except ValueError:
                pass
    return charges if charges else None


def parse_homo_lumo(log_path: Path | str) -> Optional[tuple[float, float]]:
    """Return (HOMO_eV, LUMO_eV) from alpha-spin eigenvalues.

    Walks the " Alpha  occ. eigenvalues --" and " Alpha virt. eigenvalues
    --" lines (Hartree) and returns the last occupied + first virtual,
    converted to eV.

    Returns None if the eigenvalues aren't printed in the log (Gaussian
    truncates default output for some methods; pass `Pop=Reg` via
    --extra-route to force the full eigenvalue list).
    """
    text = Path(log_path).read_text()
    occ_eigs: list[float] = []
    virt_eigs: list[float] = []
    for line in text.splitlines():
        m_occ = re.match(
            r"\s+Alpha\s+occ\.\s+eigenvalues\s+--\s+(.+)", line
        )
        if m_occ:
            occ_eigs.extend(float(x) for x in m_occ.group(1).split())
            continue
        m_virt = re.match(
            r"\s+Alpha\s+virt\.\s+eigenvalues\s+--\s+(.+)", line
        )
        if m_virt:
            virt_eigs.extend(float(x) for x in m_virt.group(1).split())
    if not occ_eigs or not virt_eigs:
        return None
    return occ_eigs[-1] * HARTREE_EV, virt_eigs[0] * HARTREE_EV


__all__ = [
    "HARTREE_EV",
    "parse_thermochem",
    "parse_mulliken_charges",
    "parse_homo_lumo",
]
