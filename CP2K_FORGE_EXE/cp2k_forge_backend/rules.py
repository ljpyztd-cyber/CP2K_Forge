from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SOFT_ELEMENTS = {"Na", "Mg", "F"}
LANTHANIDE_ELEMENTS = {
    "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd",
    "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
}
LNPP1_BASIS_BY_ELEMENT = {
    element: "DZV-MOLOPT-GTH" if element == "La" else "DZV-MOLOPT-SR-GTH"
    for element in LANTHANIDE_ELEMENTS
}
LNPP1_POTENTIAL_BY_ELEMENT = {
    "La": "GTH-PBE-q11",
    "Ce": "GTH-PBE-q12",
    "Pr": "GTH-PBE-q13",
    "Nd": "GTH-PBE-q14",
    "Pm": "GTH-PBE-q15",
    "Sm": "GTH-PBE-q16",
    "Eu": "GTH-PBE-q17",
    "Gd": "GTH-PBE-q18",
    "Tb": "GTH-PBE-q29",
    "Dy": "GTH-PBE-q30",
    "Ho": "GTH-PBE-q31",
    "Er": "GTH-PBE-q32",
    "Tm": "GTH-PBE-q33",
    "Yb": "GTH-PBE-q34",
    "Lu": "GTH-PBE-q35",
}
MAGNETIC_MOMENT_PRESETS = {
    "Mn": "2",
    "Fe": "2",
    "Co": "2",
    "Ni": "2",
}
DFT_U_PRESETS = {
    "Mn": "3.7",
    "V": "3.25",
    "Cr": "3.7",
    "Fe": "3.6",
    "Co": "5.6",
    "Ni": "6.6",
    "Mo": "4.38",
    "W": "6.2",
    "Ce": "f 4.08",
    "U": "f 2.0",
}
SCF_ACCURACY_CHOICES = {"Ultrafine", "Fine", "Medium", "Low", "Acceptable"}

_ELEMENT_SYMBOLS = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
]
ATOMIC_NUMBERS = {symbol: idx + 1 for idx, symbol in enumerate(_ELEMENT_SYMBOLS)}


@dataclass
class RuleMessage:
    level: str
    text: str


@dataclass
class NormalizedSpec:
    values: dict[str, Any]
    messages: list[RuleMessage] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)


def _symbol_from_token(token: str) -> str | None:
    token = token.strip().strip("'\"")
    match = re.match(r"([A-Z][a-z]?|[a-z])", token)
    if not match:
        return None
    symbol = match.group(1)
    return symbol[0].upper() + symbol[1:].lower()


def detect_element_counts(filename: str, text: str) -> dict[str, int]:
    suffix = Path(filename).suffix.lower()
    counts: dict[str, int] = {}

    def add(symbol: str | None) -> None:
        if symbol:
            counts[symbol] = counts.get(symbol, 0) + 1

    lines = text.splitlines()
    if suffix == ".xyz":
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 4:
                add(_symbol_from_token(parts[0]))
        return counts

    if suffix == ".pdb":
        for line in lines:
            if line.startswith(("ATOM", "HETATM")):
                symbol = line[76:78].strip() if len(line) >= 78 else ""
                if not symbol:
                    symbol = re.sub(r"[^A-Za-z]", "", line[12:16]).strip()[:2]
                add(_symbol_from_token(symbol))
        return counts

    if suffix in {".cif", ".mcif"}:
        atom_headers: list[str] = []
        in_loop = False
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower() == "loop_":
                in_loop = True
                atom_headers = []
                continue
            if in_loop and stripped.startswith("_atom_site"):
                atom_headers.append(stripped)
                continue
            if in_loop and atom_headers and not stripped.startswith("_"):
                parts = stripped.split()
                header_names = []
                for header in atom_headers:
                    name = header.split(".")[-1]
                    if name.startswith("_atom_site_"):
                        if name.startswith("_atom_site_"):
                            name = name[len("_atom_site_") :]
                    header_names.append(name)
                symbol_idx = None
                for candidate in ("type_symbol", "label"):
                    if candidate in header_names:
                        symbol_idx = header_names.index(candidate)
                        break
                if symbol_idx is not None and symbol_idx < len(parts):
                    add(_symbol_from_token(parts[symbol_idx]))
                continue
            if in_loop and atom_headers and stripped.startswith("_") and not stripped.startswith("_atom_site"):
                in_loop = False
        return counts

    for line in lines:
        parts = line.split()
        if len(parts) >= 4:
            add(_symbol_from_token(parts[0]))
    return counts


def detect_elements(filename: str, text: str) -> list[str]:
    return list(detect_element_counts(filename, text))


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float_value(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return default


def _total_electron_count(element_counts: dict[str, int], charge: int) -> int | None:
    total = 0
    for element, count in element_counts.items():
        atomic_number = ATOMIC_NUMBERS.get(element)
        if atomic_number is None:
            return None
        total += atomic_number * count
    return total - charge


def _apply_auto_multiplicity(
    values: dict[str, Any], element_counts: dict[str, int], messages: list[RuleMessage]
) -> None:
    charge = _int_value(values.get("charge", "0"), 0)
    rows = parse_key_value_rows(str(values.get("magnetization_rows", "")))
    electron_count = _total_electron_count(element_counts, charge)

    if rows:
        net_magnetization = 0.0
        used_rows: list[str] = []
        for row in rows:
            moment = _float_value(row["value"])
            if moment is None:
                messages.append(RuleMessage("warning", f"Magnetization row for {row['key']} was ignored because the moment is not numeric."))
                continue
            count = element_counts.get(row["key"], 0)
            if count == 0:
                messages.append(RuleMessage("warning", f"Magnetization row for {row['key']} did not match any detected element."))
                continue
            net_magnetization += moment * count
            used_rows.append(f"{row['key']} {moment:g} x {count}")

        spin_delta = int(round(abs(net_magnetization)))
        if electron_count is not None and spin_delta % 2 != electron_count % 2:
            old_spin_delta = spin_delta
            spin_delta += 1
            messages.append(
                RuleMessage(
                    "warning",
                    f"Auto multiplicity adjusted spin difference from {old_spin_delta} to {spin_delta} to match electron-count parity.",
                )
            )
        values["multiplicity"] = str(spin_delta + 1)
        values["uks"] = True
        if used_rows:
            messages.append(
                RuleMessage(
                    "info",
                    f"Auto multiplicity set to {spin_delta + 1} from net initial magnetization ({'; '.join(used_rows)}).",
                )
            )
        return

    if charge != 0 and electron_count is not None:
        spin_delta = abs(electron_count % 2)
        values["multiplicity"] = str(spin_delta + 1)
        if spin_delta:
            values["uks"] = True
        messages.append(
            RuleMessage(
                "info",
                f"Charge is {charge}; auto multiplicity set to {spin_delta + 1} from electron-count parity.",
            )
        )
    else:
        values["multiplicity"] = "AUTO"


def _apply_magnetism_presets(values: dict[str, Any], elements: list[str], messages: list[RuleMessage]) -> None:
    if str(values.get("magnetization_rows", "")).strip():
        return
    if not _bool_value(values.get("enable_magnetism", values.get("auto_magnetization_presets", False))):
        return
    magnetic_elements = [element for element in elements if element in MAGNETIC_MOMENT_PRESETS]
    if not magnetic_elements:
        return
    values["magnetization_rows"] = "\n".join(
        f"{element} {MAGNETIC_MOMENT_PRESETS[element]}" for element in magnetic_elements
    )
    values["uks"] = True
    messages.append(
        RuleMessage(
            "info",
            "Magnetism enabled. Suggested initial magnetization entries were added; edit them if needed.",
        )
    )


def _apply_dft_u_presets(values: dict[str, Any], elements: list[str], messages: list[RuleMessage]) -> None:
    if str(values.get("dft_u_rows", "")).strip():
        return
    if not _bool_value(values.get("enable_dft_u", values.get("auto_dft_u_presets", False))):
        return
    u_elements = [element for element in elements if element in DFT_U_PRESETS]
    if not u_elements:
        return
    values["dft_u_rows"] = "\n".join(f"{element} {DFT_U_PRESETS[element]}" for element in u_elements)
    messages.append(
        RuleMessage(
            "info",
            "DFT+U enabled. Suggested entries were added for detected elements; edit them if needed.",
        )
    )


def normalize_spec(
    raw_values: dict[str, Any], elements: list[str], element_counts: dict[str, int] | None = None
) -> NormalizedSpec:
    values = dict(raw_values)
    messages: list[RuleMessage] = []
    element_counts = dict(element_counts or {element: 1 for element in elements})
    values["enable_dft_u"] = _bool_value(values.get("enable_dft_u", values.get("auto_dft_u_presets", False)))
    values["enable_magnetism"] = _bool_value(values.get("enable_magnetism", values.get("auto_magnetization_presets", False)))
    values["lanthanide_strategy"] = _bool_value(values.get("lanthanide_strategy", False))
    values.pop("auto_dft_u_presets", None)
    values.pop("auto_magnetization_presets", None)

    lanthanides_present = sorted(LANTHANIDE_ELEMENTS.intersection(elements), key=lambda item: ATOMIC_NUMBERS[item])
    if values["lanthanide_strategy"] and lanthanides_present:
        values.update(
            {
                "scf_method": "OT",
                "ot_minimizer": "CG",
                "ot_inner_max_scf": "50",
                "cutoff": "600",
                "rel_cutoff": "60",
            }
        )
        messages.append(
            RuleMessage(
                "info",
                "LnPP1 preset enabled for "
                + ", ".join(lanthanides_present)
                + ". OT/CG, inner MAX_SCF 50, CUTOFF 600 Ry and REL_CUTOFF 60 Ry will be used; the selected SCF accuracy is preserved. "
                "Ensure BASIS_MOLOPT_LnPP1 and POTENTIAL+LnPP1 are available to CP2K.",
            )
        )
    elif values["lanthanide_strategy"]:
        messages.append(
            RuleMessage(
                "warning",
                "The LnPP1 preset was enabled, but no lanthanide element (La-Lu) was detected; no LnPP1 KIND patch will be applied.",
            )
        )
    elif lanthanides_present:
        messages.append(
            RuleMessage(
                "info",
                "Lanthanide element(s) detected: "
                + ", ".join(lanthanides_present)
                + ". The validated LnPP1 preset is available but currently disabled.",
            )
        )

    scf_method = str(values.get("scf_method", "OT")).strip().upper()
    values["scf_method"] = "DIAG" if scf_method in {"DIAG", "DIAGONALIZATION"} else "OT"

    values["add_mos_for_pdos"] = _bool_value(values.get("add_mos_for_pdos", False))
    if values["add_mos_for_pdos"] and values["scf_method"] != "DIAG":
        values["add_mos_for_pdos"] = False
        messages.append(
            RuleMessage(
                "warning",
                "Add MOS for PDOS is only available with diagonalization, so it was disabled for OT.",
            )
        )
    elif values["add_mos_for_pdos"] and _int_value(values.get("added_mos", "0"), 0) <= 0:
        values["added_mos"] = "30"

    scf_method = values["scf_method"]
    task = values.get("task", "ENERGY")
    if task == "CELL_OPT" and str(values.get("functional", "")).strip() in {"", "PBE"}:
        values["functional"] = "PBEsol"
        messages.append(RuleMessage("info", "CELL_OPT defaults to PBEsol in this preset."))

    model_size = str(values.get("model_size", "SMALL")).upper()
    if task in {"GEO_OPT", "CELL_OPT"}:
        values["geo_optimizer"] = "LBFGS" if model_size == "LARGE" else "BFGS"
    else:
        values["fixed_atoms"] = ""

    _apply_magnetism_presets(values, elements, messages)
    _apply_dft_u_presets(values, elements, messages)
    _apply_auto_multiplicity(values, element_counts, messages)

    accuracy = str(values.get("scf_accuracy", "Medium")).strip() or "Medium"
    if accuracy == "Screening":
        accuracy = "Acceptable"
    values["scf_accuracy"] = accuracy if accuracy in SCF_ACCURACY_CHOICES else "Medium"
    kpoints_mode = values.get("kpoints_mode", "GAMMA")
    smearing = bool(values.get("smearing"))
    if scf_method == "OT":
        if smearing:
            values["smearing"] = False
            messages.append(
                RuleMessage(
                    "warning",
                    "OT does not work with smearing in this preset. Smearing was disabled; use diagonalization for metallic systems.",
                )
            )
        if kpoints_mode != "GAMMA":
            values["kpoints_mode"] = "GAMMA"
            values["kpoints"] = "1,1,1"
            messages.append(
                RuleMessage(
                    "warning",
                    "OT is kept on a Gamma-only preset here. Multi-k-point calculations were reset to Gamma.",
                )
            )

    if bool(values.get("smearing")) and scf_method != "DIAG":
        values["scf_method"] = "DIAG"
        messages.append(
            RuleMessage(
                "warning",
                "Smearing requires the diagonalization path in this tool, so SCF was switched to diagonalization.",
            )
        )

    soft_present = sorted(SOFT_ELEMENTS.intersection(elements))
    if soft_present and bool(values.get("soft_element_strategy", False)):
        messages.append(
            RuleMessage(
                "info",
                "Na/Mg/F detected. GAPW + all-electron pob-DZVP-rev2 will be used for selected soft elements to avoid pushing CUTOFF unnecessarily high.",
            )
        )
    elif soft_present:
        messages.append(
            RuleMessage(
                "info",
                "Na/Mg/F detected. GAPW all-electron strategy is available but currently disabled.",
            )
        )

    if values.get("periodic") in {"NONE", "X", "Y", "Z"} and values.get("poisson_solver") == "PERIODIC":
        messages.append(
            RuleMessage(
                "warning",
                "The selected Poisson solver is PERIODIC while the geometry is not fully periodic. Consider ANALYTIC or WAVELET where appropriate.",
            )
        )

    return NormalizedSpec(values=values, messages=messages, elements=elements)


def int_or_default(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_key_value_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = re.split(r"[\s,;]+", stripped)
        if len(parts) >= 2:
            rows.append({"key": parts[0], "value": parts[1]})
    return rows


def parse_dft_u_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = re.split(r"[\s,;]+", stripped)
        if len(parts) == 2:
            rows.append({"kind": parts[0], "l": "2", "u": parts[1]})
        elif len(parts) >= 3:
            orbital = parts[1].lower()
            if orbital == "d":
                l_value = "2"
            elif orbital == "f":
                l_value = "3"
            else:
                l_value = parts[1]
            rows.append({"kind": parts[0], "l": l_value, "u": parts[2]})
    return rows
