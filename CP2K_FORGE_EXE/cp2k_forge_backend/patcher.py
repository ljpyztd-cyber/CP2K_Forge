from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .rules import SOFT_ELEMENTS, parse_dft_u_rows, parse_key_value_rows


CP2K_FORGE_WATERMARK = "#Revised by CP2K_Forge (Contact: jiapeili-c@my.cityu.edu.hk for more details)"
GEOMETRY_OPT_TASKS = {"GEO_OPT", "CELL_OPT"}


@dataclass
class PatchResult:
    text: str
    notes: list[str] = field(default_factory=list)


def _section_start(line: str, name: str) -> bool:
    return bool(re.match(rf"^\s*&{re.escape(name)}(?:\s|$)", line, flags=re.IGNORECASE))


def _section_end(line: str, name: str) -> bool:
    return bool(re.match(rf"^\s*&END\s+{re.escape(name)}(?:\s|$)", line, flags=re.IGNORECASE))


def _section_start_name(line: str) -> str | None:
    match = re.match(r"^\s*&([A-Z0-9_]+)(?:\s|$)", line, flags=re.IGNORECASE)
    if not match:
        return None
    name = match.group(1).upper()
    return None if name == "END" else name


def _section_end_name(line: str) -> str | None:
    match = re.match(r"^\s*&END(?:\s+([A-Z0-9_]+))?(?:\s|$)", line, flags=re.IGNORECASE)
    if not match:
        return None
    return (match.group(1) or "").upper()


def _find_first_section(lines: list[str], name: str) -> tuple[int, int] | None:
    start = None
    for idx, line in enumerate(lines):
        if start is None and _section_start(line, name):
            start = idx
            continue
        if start is not None and _section_end(line, name):
            return start, idx
    return None


def _find_child_section(lines: list[str], parent_start: int, parent_end: int, name: str) -> tuple[int, int] | None:
    target = name.upper()
    depth = 0
    for idx in range(parent_start + 1, parent_end):
        start_name = _section_start_name(lines[idx])
        if start_name:
            if depth == 0 and start_name == target:
                inner_depth = 0
                for end_idx in range(idx + 1, parent_end):
                    nested_start = _section_start_name(lines[end_idx])
                    if nested_start:
                        inner_depth += 1
                        continue
                    end_name = _section_end_name(lines[end_idx])
                    if end_name is None:
                        continue
                    if inner_depth == 0 and end_name in {target, ""}:
                        return idx, end_idx
                    if inner_depth > 0:
                        inner_depth -= 1
                return None
            depth += 1
            continue
        if _section_end_name(lines[idx]) is not None and depth > 0:
            depth -= 1
    return None


def _find_kind_sections(lines: list[str]) -> list[tuple[int, int, str]]:
    sections: list[tuple[int, int, str]] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*&KIND\s+(\S+)", lines[idx], flags=re.IGNORECASE)
        if not match:
            idx += 1
            continue
        name = match.group(1)
        end = idx + 1
        while end < len(lines) and not _section_end(lines[end], "KIND"):
            end += 1
        if end < len(lines):
            sections.append((idx, end, name))
        idx = end + 1
    return sections


def _block_contains(lines: list[str], start: int, end: int, pattern: str) -> bool:
    rx = re.compile(pattern, flags=re.IGNORECASE)
    return any(rx.search(line) for line in lines[start : end + 1])


def _insert_after_section_start(
    lines: list[str], section: str, insert_line: str, notes: list[str], note: str
) -> None:
    bounds = _find_first_section(lines, section)
    if not bounds:
        return
    start, end = bounds
    if insert_line.strip() in {line.strip() for line in lines[start : end + 1]}:
        return
    lines.insert(start + 1, insert_line)
    notes.append(note)


def _set_keyword_in_block(
    lines: list[str],
    start: int,
    end: int,
    keyword: str,
    value: str,
    indent: str,
    notes: list[str],
    note: str,
) -> int:
    rx = re.compile(rf"^(\s*)#?\s*{re.escape(keyword)}(?:\s+.*)?$", flags=re.IGNORECASE)
    for idx in range(start + 1, end):
        if rx.match(lines[idx]):
            old = lines[idx].strip()
            lines[idx] = f"{indent}{keyword} {value}"
            if lines[idx].strip() != old:
                notes.append(note)
            return 0
    lines.insert(start + 1, f"{indent}{keyword} {value}")
    notes.append(note)
    return 1


def _set_lone_keyword_in_block(
    lines: list[str],
    start: int,
    end: int,
    keyword: str,
    indent: str,
    notes: list[str],
    note: str,
) -> int:
    rx = re.compile(rf"^(\s*)#?\s*{re.escape(keyword)}(?:\s+.*)?$", flags=re.IGNORECASE)
    for idx in range(start + 1, end):
        if rx.match(lines[idx]):
            old = lines[idx].strip()
            lines[idx] = f"{indent}{keyword}"
            if lines[idx].strip() != old:
                notes.append(note)
            return 0
    lines.insert(start + 1, f"{indent}{keyword}")
    notes.append(note)
    return 1


def _remove_section(lines: list[str], name: str, notes: list[str], note: str) -> None:
    while True:
        bounds = _find_first_section(lines, name)
        if not bounds:
            break
        start, end = bounds
        del lines[start : end + 1]
        notes.append(note)


def _kind_element(lines: list[str], start: int, end: int, kind_name: str) -> str:
    for idx in range(start + 1, end):
        match = re.match(r"^\s*ELEMENT\s+(\S+)", lines[idx], flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return kind_name.split("_")[0]


def _ensure_qs_keyword(lines: list[str], keyword_line: str, notes: list[str], note: str) -> None:
    bounds = _find_first_section(lines, "QS")
    if not bounds:
        return
    start, end = bounds
    key = keyword_line.split()[0]
    if _block_contains(lines, start, end, rf"^\s*{re.escape(key)}\b"):
        return
    lines.insert(start + 1, keyword_line)
    notes.append(note)


def _set_qs_method(lines: list[str], method: str, notes: list[str], note: str) -> None:
    bounds = _find_first_section(lines, "QS")
    if not bounds:
        return
    start, end = bounds
    changed = _set_keyword_in_block(lines, start, end, "METHOD", method, "      ", notes, note)
    if changed:
        return


def _set_dft_keyword(lines: list[str], keyword: str, value: str, notes: list[str], note: str) -> None:
    dft = _find_first_section(lines, "DFT")
    if not dft:
        return
    start, end = dft
    _set_keyword_in_block(lines, start, end, keyword, value, "    ", notes, note)


def _set_dft_lone_keyword(lines: list[str], keyword: str, notes: list[str], note: str) -> None:
    dft = _find_first_section(lines, "DFT")
    if not dft:
        return
    start, end = dft
    _set_lone_keyword_in_block(lines, start, end, keyword, "    ", notes, note)


def _apply_charge_spin_keywords(lines: list[str], values: dict[str, Any], notes: list[str]) -> None:
    charge = str(values.get("charge", "0")).strip()
    if charge and charge != "0":
        _set_dft_keyword(lines, "CHARGE", charge, notes, "Set total charge.")

    multiplicity = str(values.get("multiplicity", "AUTO")).strip()
    if multiplicity.upper() not in {"", "AUTO", "DEFAULT", "0"}:
        _set_dft_keyword(lines, "MULTIPLICITY", multiplicity, notes, "Set spin multiplicity.")

    try:
        mult_value = int(multiplicity)
    except ValueError:
        mult_value = 1
    if bool(values.get("uks")) or mult_value > 1 or str(values.get("magnetization_rows", "")).strip():
        _set_dft_lone_keyword(lines, "UKS", notes, "Enabled UKS for spin-polarized setup.")


def _ensure_kpoints(lines: list[str], kpoints: str, notes: list[str]) -> None:
    if _find_first_section(lines, "KPOINTS"):
        return
    dft = _find_first_section(lines, "DFT")
    if not dft:
        return
    start, _end = dft
    parts = re.split(r"[\s,]+", kpoints.strip())
    if len(parts) != 3:
        return
    block = [
        "    &KPOINTS",
        f"      SCHEME MONKHORST-PACK {parts[0]} {parts[1]} {parts[2]}",
        "    &END KPOINTS",
    ]
    lines[start + 1 : start + 1] = block
    notes.append(f"Added Monkhorst-Pack k-points: {kpoints}")


def _ensure_smearing(lines: list[str], values: dict[str, Any], notes: list[str]) -> None:
    if not values.get("smearing"):
        return
    scf = _find_first_section(lines, "SCF")
    if not scf:
        return
    start, end = scf
    if not _block_contains(lines, start, end, r"^\s*&SMEAR\b"):
        temperature = str(values.get("electronic_temperature", "300")).strip() or "300"
        block = [
            "      &SMEAR ON",
            "        METHOD FERMI_DIRAC",
            f"        ELECTRONIC_TEMPERATURE [K] {temperature}",
            "      &END SMEAR",
        ]
        lines[start + 1 : start + 1] = block
        notes.append("Added FERMI_DIRAC smearing block.")


def _ensure_outer_scf(lines: list[str], notes: list[str]) -> tuple[int, int] | None:
    outer = _find_first_section(lines, "OUTER_SCF")
    if outer:
        return outer
    scf = _find_first_section(lines, "SCF")
    if not scf:
        return None
    _start, end = scf
    block = [
        "      &OUTER_SCF",
        "      &END OUTER_SCF",
    ]
    lines[end:end] = block
    notes.append("Added OUTER_SCF block for OT.")
    return end, end + 1


def _apply_dft_u(lines: list[str], values: dict[str, Any], notes: list[str]) -> None:
    rows = parse_dft_u_rows(str(values.get("dft_u_rows", "")))
    if not rows:
        return
    dft = _find_first_section(lines, "DFT")
    if dft:
        start, end = dft
        _set_keyword_in_block(
            lines,
            start,
            end,
            "PLUS_U_METHOD",
            str(values.get("plus_u_method", "MULLIKEN")),
            "    ",
            notes,
            "Set PLUS_U_METHOD for DFT+U.",
        )

    row_by_kind = {row["kind"]: row for row in rows}
    for start, end, kind_name in reversed(_find_kind_sections(lines)):
        element = _kind_element(lines, start, end, kind_name)
        row = row_by_kind.get(kind_name) or row_by_kind.get(element)
        if not row:
            continue
        if _block_contains(lines, start, end, r"^\s*&DFT_PLUS_U\b"):
            continue
        block = [
            "      &DFT_PLUS_U",
            f"        L {row['l']}",
            f"        U_MINUS_J [eV] {row['u']}",
            "      &END DFT_PLUS_U",
        ]
        lines[end:end] = block
        notes.append(f"Added DFT+U for {kind_name}: L={row['l']}, U={row['u']} eV.")


def _apply_magnetization(lines: list[str], values: dict[str, Any], notes: list[str]) -> None:
    rows = parse_key_value_rows(str(values.get("magnetization_rows", "")))
    if not rows:
        return
    mag_by_kind = {row["key"]: row["value"] for row in rows}
    for start, end, kind_name in reversed(_find_kind_sections(lines)):
        element = _kind_element(lines, start, end, kind_name)
        value = mag_by_kind.get(kind_name) or mag_by_kind.get(element)
        if value is None:
            continue
        inserted = _set_keyword_in_block(
            lines,
            start,
            end,
            "MAGNETIZATION",
            value,
            "      ",
            notes,
            f"Set initial magnetization for {kind_name}.",
        )
        end += inserted


def _apply_soft_element_strategy(lines: list[str], elements: list[str], notes: list[str]) -> None:
    soft_present = SOFT_ELEMENTS.intersection(elements)
    if not soft_present:
        return
    _insert_after_section_start(
        lines,
        "DFT",
        "    BASIS_SET_FILE_NAME  BASIS_pob",
        notes,
        "Added BASIS_SET_FILE_NAME BASIS_pob for Na/Mg/F all-electron basis.",
    )
    _set_qs_method(lines, "GAPW", notes, "Set METHOD GAPW for Na/Mg/F all-electron treatment.")

    for start, end, kind_name in _find_kind_sections(lines):
        element = _kind_element(lines, start, end, kind_name)
        if element not in soft_present:
            continue
        for idx in range(start + 1, end):
            if re.match(r"^\s*BASIS_SET\b", lines[idx], flags=re.IGNORECASE):
                lines[idx] = "      BASIS_SET pob-DZVP-rev2"
                notes.append(f"Changed {kind_name} BASIS_SET to pob-DZVP-rev2.")
            elif re.match(r"^\s*POTENTIAL\b", lines[idx], flags=re.IGNORECASE):
                lines[idx] = "      POTENTIAL ALL"
                notes.append(f"Changed {kind_name} POTENTIAL to ALL.")


def _ensure_cp2k_forge_watermark(lines: list[str], notes: list[str]) -> None:
    if any(line.strip() == CP2K_FORGE_WATERMARK for line in lines):
        return
    for idx, line in enumerate(lines):
        if re.match(r"^\s*#\s*Generated by Multiwfn\b", line, flags=re.IGNORECASE):
            lines.insert(idx + 1, CP2K_FORGE_WATERMARK)
            notes.append("Added CP2K_Forge revision watermark.")
            return
    lines.insert(0, CP2K_FORGE_WATERMARK)
    notes.append("Added CP2K_Forge revision watermark.")


def _is_geometry_optimization_task(values: dict[str, Any]) -> bool:
    return str(values.get("task", "")).strip().upper() in GEOMETRY_OPT_TASKS


def _uses_ot(values: dict[str, Any]) -> bool:
    return str(values.get("scf_method", "")).strip().upper() == "OT"


def _wants_molden_print(values: dict[str, Any]) -> bool:
    return bool(values.get("molden_print", values.get("output_molden", False)))


def _ensure_ignore_convergence_failure_for_optimization(lines: list[str], notes: list[str]) -> None:
    scf = _find_first_section(lines, "SCF")
    if not scf:
        return
    start, end = scf
    active_rx = re.compile(r"^\s*IGNORE_CONVERGENCE_FAILURE\b", flags=re.IGNORECASE)
    commented_rx = re.compile(r"^\s*#\s*(IGNORE_CONVERGENCE_FAILURE\b.*)$", flags=re.IGNORECASE)

    if any(active_rx.match(line) for line in lines[start + 1 : end]):
        return

    for idx in range(start + 1, end):
        match = commented_rx.match(lines[idx])
        if not match:
            continue
        lines[idx] = f"      {match.group(1).strip()}"
        notes.append("Uncommented IGNORE_CONVERGENCE_FAILURE for geometry optimization.")
        return

    lines.insert(start + 1, "      IGNORE_CONVERGENCE_FAILURE")
    notes.append("Added IGNORE_CONVERGENCE_FAILURE for geometry optimization.")


def _ensure_ot_molden_mo_energy_print(lines: list[str], notes: list[str]) -> None:
    dft = _find_first_section(lines, "DFT")
    if not dft:
        return

    dft_start, dft_end = dft
    dft_print = _find_child_section(lines, dft_start, dft_end, "PRINT")
    if not dft_print:
        block = [
            "    &PRINT",
            "    &END PRINT",
        ]
        lines[dft_end:dft_end] = block
        notes.append("Added DFT PRINT block for OT Molden MO energies.")
        dft = _find_first_section(lines, "DFT")
        if not dft:
            return
        dft_start, dft_end = dft
        dft_print = _find_child_section(lines, dft_start, dft_end, "PRINT")
        if not dft_print:
            return

    print_start, print_end = dft_print
    mo = _find_child_section(lines, print_start, print_end, "MO")
    if not mo:
        block = [
            "      &MO",
            "        ENERGIES T",
            "        OCCUPATION_NUMBERS T",
            "        &EACH",
            "          QS_SCF 0",
            "        &END EACH",
            "      &END MO",
        ]
        lines[print_end:print_end] = block
        notes.append("Added MO energy print block for OT Molden support.")
        return

    mo_start, mo_end = mo
    inserted = _set_keyword_in_block(
        lines,
        mo_start,
        mo_end,
        "ENERGIES",
        "T",
        "        ",
        notes,
        "Enabled MO energy printing for OT Molden support.",
    )
    mo_end += inserted
    inserted = _set_keyword_in_block(
        lines,
        mo_start,
        mo_end,
        "OCCUPATION_NUMBERS",
        "T",
        "        ",
        notes,
        "Enabled MO occupation printing for OT Molden support.",
    )
    mo_end += inserted

    each = _find_child_section(lines, mo_start, mo_end, "EACH")
    if not each:
        block = [
            "        &EACH",
            "          QS_SCF 0",
            "        &END EACH",
        ]
        lines[mo_end:mo_end] = block
        notes.append("Added MO EACH block for OT Molden support.")
        return

    each_start, each_end = each
    _set_keyword_in_block(
        lines,
        each_start,
        each_end,
        "QS_SCF",
        "0",
        "          ",
        notes,
        "Set MO energy print frequency for OT Molden support.",
    )


def apply_cp2k_forge_patches(raw_text: str, values: dict[str, Any], elements: list[str]) -> PatchResult:
    lines = raw_text.splitlines()
    notes: list[str] = []
    _ensure_cp2k_forge_watermark(lines, notes)

    _insert_after_section_start(
        lines,
        "GLOBAL",
        "  EXTENDED_FFT_LENGTHS",
        notes,
        "Added EXTENDED_FFT_LENGTHS.",
    )
    _apply_charge_spin_keywords(lines, values, notes)

    if _is_geometry_optimization_task(values):
        _ensure_ignore_convergence_failure_for_optimization(lines, notes)

    if _uses_ot(values):
        ot = _find_first_section(lines, "OT")
        if ot:
            start, end = ot
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "PRECONDITIONER",
                "FULL_ALL",
                "        ",
                notes,
                "Set OT PRECONDITIONER FULL_ALL.",
            )
            end += inserted
            _set_keyword_in_block(
                lines,
                start,
                end,
                "ALGORITHM",
                "IRAC",
                "        ",
                notes,
                "Set OT ALGORITHM IRAC.",
            )
        scf = _find_first_section(lines, "SCF")
        if scf:
            start, end = scf
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "MAX_SCF",
                str(values.get("ot_inner_max_scf", "128")),
                "      ",
                notes,
                "Set OT inner MAX_SCF.",
            )
            end += inserted
            _set_keyword_in_block(
                lines,
                start,
                end,
                "EPS_SCF",
                str(values.get("ot_inner_eps_scf", "5.0E-06")),
                "      ",
                notes,
                "Set OT inner EPS_SCF.",
            )
        outer = _ensure_outer_scf(lines, notes)
        if outer:
            start, end = outer
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "MAX_SCF",
                str(values.get("ot_outer_max_scf", "20")),
                "        ",
                notes,
                "Set OT outer MAX_SCF.",
            )
            end += inserted
            _set_keyword_in_block(
                lines,
                start,
                end,
                "EPS_SCF",
                str(values.get("ot_outer_eps_scf", "5.0E-06")),
                "        ",
                notes,
                "Set OT outer EPS_SCF.",
            )
        if _is_geometry_optimization_task(values) and not (
            values.get("soft_element_strategy", False) and SOFT_ELEMENTS.intersection(elements)
        ):
            _ensure_qs_keyword(
                lines,
                "      EXTRAPOLATION USE_PREV_P",
                notes,
                "Added EXTRAPOLATION USE_PREV_P for optimization.",
            )
    else:
        scf = _find_first_section(lines, "SCF")
        if scf:
            start, end = scf
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "MAX_SCF",
                str(values.get("diag_max_scf", "1280")),
                "      ",
                notes,
                "Expanded diagonalization MAX_SCF.",
            )
            end += inserted
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "EPS_SCF",
                str(values.get("diag_eps_scf", "5.0E-06")),
                "      ",
                notes,
                "Set diagonalization EPS_SCF.",
            )
            end += inserted
        mixing = _find_first_section(lines, "MIXING")
        if mixing:
            start, end = mixing
            inserted = _set_keyword_in_block(
                lines,
                start,
                end,
                "ALPHA",
                str(values.get("mixing_alpha", "0.2")),
                "        ",
                notes,
                "Adjusted mixing ALPHA.",
            )
            end += inserted
            _set_keyword_in_block(
                lines,
                start,
                end,
                "NBROYDEN",
                str(values.get("nbroyden", "16")),
                "        ",
                notes,
                "Adjusted NBROYDEN.",
            )

    if values.get("soft_element_strategy", False):
        _apply_soft_element_strategy(lines, elements, notes)

    if values.get("kpoints_mode", "GAMMA") != "GAMMA":
        _ensure_kpoints(lines, str(values.get("kpoints", "1,1,1")), notes)

    _ensure_smearing(lines, values, notes)

    if _uses_ot(values) and _wants_molden_print(values):
        _ensure_ot_molden_mo_energy_print(lines, notes)

    if not _wants_molden_print(values):
        _remove_section(lines, "MO_MOLDEN", notes, "Removed MO_MOLDEN block.")

    _apply_dft_u(lines, values, notes)
    _apply_magnetization(lines, values, notes)

    return PatchResult(text="\n".join(lines).rstrip() + "\n", notes=notes)
