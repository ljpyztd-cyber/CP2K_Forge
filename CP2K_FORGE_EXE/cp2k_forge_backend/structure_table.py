from __future__ import annotations

import re
from statistics import median
from math import sqrt
from typing import Any, Iterable


FLOAT_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$")
CHARGE_MULT_RE = re.compile(r"^\s*[+-]?\d+\s+\d+\s*$")


def _as_float(text: str) -> float:
    return float(text.replace("D", "E").replace("d", "e"))


def _is_float(text: str) -> bool:
    return bool(FLOAT_RE.match(text.strip()))


def _symbol_from_token(token: str) -> str:
    token = token.strip()
    if token.lower() == "tv":
        return "Tv"
    match = re.match(r"([A-Z][a-z]?|[a-z])", token)
    if not match:
        return token
    symbol = match.group(1)
    return symbol[0].upper() + symbol[1:].lower()


def _atoms_from_table(atom_table: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(atom_table, dict):
        atoms = atom_table.get("atoms", [])
    else:
        atoms = atom_table
    return [dict(atom) for atom in atoms]


def parse_gjf_atom_table(content: str, source_name: str = "", source_path: str = "") -> dict[str, Any]:
    """Parse a Multiwfn 100-2 style GJF and return a 1-based real-atom table."""

    lines = content.splitlines()
    warnings: list[str] = []
    charge_line_index: int | None = None
    for idx, line in enumerate(lines):
        if CHARGE_MULT_RE.match(line):
            charge_line_index = idx
            break

    if charge_line_index is None:
        return {
            "atoms": [],
            "warnings": ["Could not find Gaussian charge/multiplicity line."],
            "source_name": source_name,
            "source_path": source_path,
            "coordinate_line_count": 0,
            "tv_count": 0,
            "real_atom_count": 0,
            "first_atom_index": None,
            "last_atom_index": None,
        }

    atoms: list[dict[str, Any]] = []
    coordinate_line_count = 0
    tv_count = 0

    for line_no, line in enumerate(lines[charge_line_index + 1 :], start=charge_line_index + 2):
        stripped = line.strip()
        if not stripped:
            break
        parts = stripped.split()
        if len(parts) < 4 or not all(_is_float(part) for part in parts[-3:]):
            warnings.append(f"Skipped non-coordinate line {line_no}: {stripped}")
            continue

        coordinate_line_count += 1
        element = _symbol_from_token(parts[0])
        x, y, z = (_as_float(parts[-3]), _as_float(parts[-2]), _as_float(parts[-1]))

        if element == "Tv":
            tv_count += 1
            continue

        atoms.append(
            {
                "index": len(atoms) + 1,
                "element": element,
                "x": x,
                "y": y,
                "z": z,
                "source_line": line_no,
                "source_gjf": source_path or source_name,
                "slab_role": "unclassified",
                "selected_as_fixed": False,
            }
        )

    if not atoms:
        warnings.append("No real atom coordinates were parsed from the GJF coordinate section.")

    return {
        "atoms": atoms,
        "warnings": warnings,
        "source_name": source_name,
        "source_path": source_path,
        "coordinate_line_count": coordinate_line_count,
        "tv_count": tv_count,
        "real_atom_count": len(atoms),
        "first_atom_index": atoms[0]["index"] if atoms else None,
        "last_atom_index": atoms[-1]["index"] if atoms else None,
    }


def _strip_fixed_atom_comments(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        line = line.split("//", 1)[0]
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def parse_fixed_atom_list(text: str, max_index: int | None = None) -> dict[str, Any]:
    """Parse fixed atom indices/ranges into a sorted unique 1-based integer list."""

    cleaned = _strip_fixed_atom_comments(text)
    tokens = [token for token in re.split(r"[\s,;]+", cleaned.strip()) if token]
    indices: set[int] = set()
    errors: list[str] = []

    for token in tokens:
        range_match = re.fullmatch(r"(\d+)-(\d+)", token)
        int_match = re.fullmatch(r"\d+", token)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start < 1 or end < 1:
                errors.append(f"Atom indices must be 1-based positive integers: {token}")
                continue
            if end < start:
                errors.append(f"Invalid descending range: {token}")
                continue
            indices.update(range(start, end + 1))
        elif int_match:
            value = int(token)
            if value < 1:
                errors.append(f"Atom indices must be 1-based positive integers: {token}")
                continue
            indices.add(value)
        else:
            errors.append(f"Invalid fixed atom token: {token}")

    sorted_indices = sorted(indices)
    out_of_range: list[int] = []
    if max_index is not None:
        out_of_range = [index for index in sorted_indices if index > max_index]
        if out_of_range:
            errors.append(f"Atom indices out of range 1..{max_index}: {compress_index_ranges(out_of_range)}")
            sorted_indices = [index for index in sorted_indices if index <= max_index]

    return {
        "indices": sorted_indices,
        "count": len(sorted_indices),
        "range_string": compress_index_ranges(sorted_indices),
        "out_of_range": out_of_range,
        "errors": errors,
        "warnings": [],
    }


def compress_index_ranges(indices: Iterable[int]) -> str:
    """Compress sorted or unsorted atom indices into CP2K-friendly ranges."""

    unique = sorted({int(index) for index in indices})
    if not unique:
        return ""

    ranges: list[str] = []
    start = previous = unique[0]
    for index in unique[1:]:
        if index == previous + 1:
            previous = index
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = index
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ",".join(ranges)


def _build_z_groups(atoms: list[dict[str, Any]], gap_threshold: float) -> list[list[dict[str, Any]]]:
    sorted_atoms = sorted(atoms, key=lambda atom: (float(atom["z"]), int(atom["index"])))
    if not sorted_atoms:
        return []

    groups: list[list[dict[str, Any]]] = [[sorted_atoms[0]]]
    previous_z = float(sorted_atoms[0]["z"])
    for atom in sorted_atoms[1:]:
        z_value = float(atom["z"])
        if z_value - previous_z >= gap_threshold:
            groups.append([])
        groups[-1].append(atom)
        previous_z = z_value
    return groups


def _group_span(group: list[dict[str, Any]]) -> float:
    if not group:
        return 0.0
    z_values = [float(atom["z"]) for atom in group]
    return max(z_values) - min(z_values)


def detect_slab_body_by_z(atom_table: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Conservatively detect slab body atoms from z-coordinate gaps."""

    atoms = _atoms_from_table(atom_table)
    warnings: list[str] = []
    if not atoms:
        return {
            "slab_body_indices": [],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [],
            "warnings": ["No atoms were supplied for slab detection."],
            "confidence": "low",
            "z_gap_threshold": None,
            "groups": [],
        }

    if len(atoms) < 4:
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [],
            "warnings": ["Too few atoms for reliable z-gap slab detection; all atoms kept as slab body."],
            "confidence": "low",
            "z_gap_threshold": None,
            "groups": [],
        }

    sorted_atoms = sorted(atoms, key=lambda atom: (float(atom["z"]), int(atom["index"])))
    gaps = [
        float(right["z"]) - float(left["z"])
        for left, right in zip(sorted_atoms, sorted_atoms[1:])
        if float(right["z"]) - float(left["z"]) > 1.0e-6
    ]

    if not gaps:
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [],
            "warnings": ["No meaningful z gaps were found; all atoms kept as slab body."],
            "confidence": "low",
            "z_gap_threshold": None,
            "groups": [],
        }

    median_gap = median(gaps)
    max_gap = max(gaps)
    gap_threshold = max(2.0, median_gap * 8.0)
    if max_gap < gap_threshold:
        warnings.append("No clear z gap was found; all atoms kept as slab body.")
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [],
            "warnings": warnings,
            "confidence": "low",
            "z_gap_threshold": gap_threshold,
            "groups": [],
        }

    groups = _build_z_groups(atoms, gap_threshold)
    if len(groups) < 2:
        warnings.append("z-gap threshold did not split the structure; all atoms kept as slab body.")
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [],
            "warnings": warnings,
            "confidence": "low",
            "z_gap_threshold": gap_threshold,
            "groups": [],
        }

    largest_group = max(groups, key=lambda group: (len(group), _group_span(group)))
    largest_count = len(largest_group)
    non_largest = [group for group in groups if group is not largest_group]

    # Conservative rule: only exclude side groups when the slab body is clearly dominant.
    if largest_count < max(4, int(0.6 * len(atoms))):
        warnings.append("z groups are not clearly dominated by one slab body; all atoms kept as slab body.")
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [int(atom["index"]) for atom in atoms],
            "warnings": warnings,
            "confidence": "low",
            "z_gap_threshold": gap_threshold,
            "groups": _summarize_groups(groups),
        }

    max_side_count = max(len(group) for group in non_largest) if non_largest else 0
    if max_side_count > max(12, int(0.25 * largest_count)):
        warnings.append("One or more non-slab z groups are too large to classify as adsorbates; all atoms kept as slab body.")
        return {
            "slab_body_indices": [int(atom["index"]) for atom in atoms],
            "probable_adsorbate_indices": [],
            "uncertain_indices": [int(atom["index"]) for atom in atoms],
            "warnings": warnings,
            "confidence": "low",
            "z_gap_threshold": gap_threshold,
            "groups": _summarize_groups(groups),
        }

    slab_indices = sorted(int(atom["index"]) for atom in largest_group)
    adsorbate_indices = sorted(
        int(atom["index"])
        for group in non_largest
        for atom in group
    )
    warnings.append(
        "Automatic slab body detection is heuristic; inspect probable adsorbates, especially for wrapped or tilted slabs."
    )
    return {
        "slab_body_indices": slab_indices,
        "probable_adsorbate_indices": adsorbate_indices,
        "uncertain_indices": [],
        "warnings": warnings,
        "confidence": "medium" if adsorbate_indices else "low",
        "z_gap_threshold": gap_threshold,
        "groups": _summarize_groups(groups),
    }


def _summarize_groups(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for group in groups:
        if not group:
            continue
        z_values = [float(atom["z"]) for atom in group]
        indices = sorted(int(atom["index"]) for atom in group)
        summary.append(
            {
                "count": len(group),
                "z_min": min(z_values),
                "z_max": max(z_values),
                "indices": indices,
                "indices_string": compress_index_ranges(indices),
            }
        )
    return summary


def _parse_excluded_indices(exclude_indices: str | Iterable[int] | None, max_index: int) -> tuple[set[int], list[str]]:
    if exclude_indices is None:
        return set(), []
    if isinstance(exclude_indices, str):
        parsed = parse_fixed_atom_list(exclude_indices, max_index=max_index)
        return set(parsed["indices"]), parsed["errors"]
    excluded = {int(index) for index in exclude_indices if int(index) >= 1}
    out_of_range = sorted(index for index in excluded if index > max_index)
    errors: list[str] = []
    if out_of_range:
        errors.append(f"Excluded atom indices out of range 1..{max_index}: {compress_index_ranges(out_of_range)}")
    return {index for index in excluded if index <= max_index}, errors


def select_freeze_bottom_z_range(
    atom_table: list[dict[str, Any]] | dict[str, Any],
    percent: float = 70.0,
    exclude_indices: str | Iterable[int] | None = None,
) -> dict[str, Any]:
    """Select fixed atoms within the bottom z-range of the detected slab body."""

    atoms = _atoms_from_table(atom_table)
    warnings: list[str] = []
    errors: list[str] = []

    if not atoms:
        return {
            "fixed_indices": [],
            "fixed_atom_string": "",
            "warnings": ["No atoms were supplied for freeze-bottom selection."],
            "errors": [],
            "preview": {},
        }

    try:
        percent_value = float(percent)
    except (TypeError, ValueError):
        percent_value = 70.0
        warnings.append("Invalid percent value; using default 70.")

    if percent_value < 0 or percent_value > 100:
        errors.append("Freeze bottom z-range percent must be between 0 and 100.")
        return {
            "fixed_indices": [],
            "fixed_atom_string": "",
            "warnings": warnings,
            "errors": errors,
            "preview": {},
        }

    max_index = max(int(atom["index"]) for atom in atoms)
    manual_excluded, exclude_errors = _parse_excluded_indices(exclude_indices, max_index)
    errors.extend(exclude_errors)

    detection = detect_slab_body_by_z(atoms)
    warnings.extend(detection.get("warnings", []))
    slab_indices = set(int(index) for index in detection.get("slab_body_indices", []))
    probable_adsorbates = set(int(index) for index in detection.get("probable_adsorbate_indices", []))
    slab_indices -= manual_excluded

    atom_by_index = {int(atom["index"]): atom for atom in atoms}
    slab_atoms = [atom_by_index[index] for index in sorted(slab_indices) if index in atom_by_index]
    if not slab_atoms:
        errors.append("No slab body atoms remain after detection/manual exclusions.")
        return {
            "fixed_indices": [],
            "fixed_atom_string": "",
            "warnings": warnings,
            "errors": errors,
            "detection": detection,
            "preview": {
                "detected_slab_atom_count": 0,
                "probable_adsorbate_atom_count": len(probable_adsorbates),
                "manual_excluded_indices": sorted(manual_excluded),
            },
        }

    z_values = [float(atom["z"]) for atom in slab_atoms]
    z_min = min(z_values)
    z_max = max(z_values)
    z_threshold = z_min + percent_value / 100.0 * (z_max - z_min)
    fixed_indices = sorted(
        int(atom["index"])
        for atom in slab_atoms
        if float(atom["z"]) <= z_threshold
    )

    fixed_atom_string = compress_index_ranges(fixed_indices)
    return {
        "fixed_indices": fixed_indices,
        "fixed_atom_string": fixed_atom_string,
        "warnings": warnings,
        "errors": errors,
        "detection": detection,
        "preview": {
            "percent": percent_value,
            "detected_slab_atom_count": len(slab_atoms),
            "probable_adsorbate_atom_count": len(probable_adsorbates),
            "manual_excluded_indices": sorted(manual_excluded),
            "manual_excluded_string": compress_index_ranges(manual_excluded),
            "probable_adsorbate_indices": sorted(probable_adsorbates),
            "probable_adsorbate_string": compress_index_ranges(probable_adsorbates),
            "z_min_slab": z_min,
            "z_max_slab": z_max,
            "z_threshold": z_threshold,
            "fixed_atom_count": len(fixed_indices),
            "fixed_atom_string": fixed_atom_string,
        },
    }


def _distance(atom_a: dict[str, Any], atom_b: dict[str, Any]) -> float:
    dx = float(atom_a["x"]) - float(atom_b["x"])
    dy = float(atom_a["y"]) - float(atom_b["y"])
    dz = float(atom_a["z"]) - float(atom_b["z"])
    return sqrt(dx * dx + dy * dy + dz * dz)


def _match_reference_atoms_to_target(
    target_atoms: list[dict[str, Any]],
    reference_atoms: list[dict[str, Any]],
    tolerance: float,
    excluded_target_indices: set[int],
) -> tuple[dict[int, int], list[int], list[str]]:
    warnings: list[str] = []
    used_target_indices: set[int] = set()
    target_by_element: dict[str, list[dict[str, Any]]] = {}
    for atom in target_atoms:
        index = int(atom["index"])
        if index in excluded_target_indices:
            continue
        target_by_element.setdefault(str(atom["element"]), []).append(atom)

    mapping: dict[int, int] = {}
    unmatched_reference_indices: list[int] = []
    for ref_atom in reference_atoms:
        ref_index = int(ref_atom["index"])
        candidates: list[tuple[float, dict[str, Any]]] = []
        for target_atom in target_by_element.get(str(ref_atom["element"]), []):
            target_index = int(target_atom["index"])
            if target_index in used_target_indices:
                continue
            distance = _distance(ref_atom, target_atom)
            if distance <= tolerance:
                candidates.append((distance, target_atom))
        if not candidates:
            unmatched_reference_indices.append(ref_index)
            continue
        candidates.sort(key=lambda item: (item[0], int(item[1]["index"])))
        if len(candidates) > 1 and abs(candidates[1][0] - candidates[0][0]) < 1.0e-4:
            warnings.append(f"Reference atom {ref_index} has ambiguous target matches; nearest match was used.")
        target_index = int(candidates[0][1]["index"])
        mapping[ref_index] = target_index
        used_target_indices.add(target_index)
    return mapping, unmatched_reference_indices, warnings


def select_freeze_bottom_z_range_from_reference(
    target_atom_table: list[dict[str, Any]] | dict[str, Any],
    reference_atom_table: list[dict[str, Any]] | dict[str, Any],
    percent: float = 70.0,
    exclude_indices: str | Iterable[int] | None = None,
    match_tolerance: float = 0.2,
) -> dict[str, Any]:
    """Select fixed atoms in a target structure by comparing with a clean slab reference."""

    target_atoms = _atoms_from_table(target_atom_table)
    reference_atoms = _atoms_from_table(reference_atom_table)
    warnings: list[str] = []
    errors: list[str] = []

    if not target_atoms:
        errors.append("No target atoms were supplied for reference-slab selection.")
    if not reference_atoms:
        errors.append("No clean slab reference atoms were supplied.")
    if errors:
        return {
            "fixed_indices": [],
            "fixed_atom_string": "",
            "warnings": warnings,
            "errors": errors,
            "preview": {},
        }

    try:
        percent_value = float(percent)
    except (TypeError, ValueError):
        percent_value = 70.0
        warnings.append("Invalid percent value; using default 70.")

    if percent_value < 0 or percent_value > 100:
        errors.append("Freeze bottom z-range percent must be between 0 and 100.")
        return {
            "fixed_indices": [],
            "fixed_atom_string": "",
            "warnings": warnings,
            "errors": errors,
            "preview": {},
        }

    max_target_index = max(int(atom["index"]) for atom in target_atoms)
    manual_excluded, exclude_errors = _parse_excluded_indices(exclude_indices, max_target_index)
    errors.extend(exclude_errors)

    try:
        tolerance_value = float(match_tolerance)
    except (TypeError, ValueError):
        tolerance_value = 0.2
        warnings.append("Invalid clean slab match tolerance; using default 0.2 Angstrom.")
    if tolerance_value <= 0:
        tolerance_value = 0.2
        warnings.append("Clean slab match tolerance must be positive; using default 0.2 Angstrom.")

    mapping, unmatched_reference_indices, match_warnings = _match_reference_atoms_to_target(
        target_atoms,
        reference_atoms,
        tolerance_value,
        manual_excluded,
    )
    warnings.extend(match_warnings)

    reference_z_values = [float(atom["z"]) for atom in reference_atoms]
    z_min = min(reference_z_values)
    z_max = max(reference_z_values)
    z_threshold = z_min + percent_value / 100.0 * (z_max - z_min)
    fixed_reference_indices = sorted(
        int(atom["index"])
        for atom in reference_atoms
        if float(atom["z"]) <= z_threshold
    )
    unmatched_fixed_reference_indices = [index for index in fixed_reference_indices if index not in mapping]
    if unmatched_fixed_reference_indices:
        errors.append(
            "Could not map these clean slab atoms to the target structure: "
            f"{compress_index_ranges(unmatched_fixed_reference_indices)}"
        )

    fixed_indices = sorted(mapping[index] for index in fixed_reference_indices if index in mapping)
    fixed_atom_string = compress_index_ranges(fixed_indices)
    mapped_target_indices = set(mapping.values())
    target_indices = {int(atom["index"]) for atom in target_atoms}
    probable_adsorbates = sorted(target_indices - mapped_target_indices - manual_excluded)

    if unmatched_reference_indices:
        warnings.append(
            "Some clean slab reference atoms were not matched to the target structure: "
            f"{compress_index_ranges(unmatched_reference_indices)}"
        )
    warnings.append(
        "Clean slab reference mode uses coordinate matching; inspect the preview if the target slab was relaxed, wrapped, or shifted."
    )

    return {
        "fixed_indices": [] if errors else fixed_indices,
        "fixed_atom_string": "" if errors else fixed_atom_string,
        "warnings": warnings,
        "errors": errors,
        "preview": {
            "mode": "reference_slab",
            "percent": percent_value,
            "match_tolerance": tolerance_value,
            "target_atom_count": len(target_atoms),
            "reference_slab_atom_count": len(reference_atoms),
            "mapped_slab_atom_count": len(mapped_target_indices),
            "detected_slab_atom_count": len(mapped_target_indices),
            "probable_adsorbate_atom_count": len(probable_adsorbates),
            "manual_excluded_indices": sorted(manual_excluded),
            "manual_excluded_string": compress_index_ranges(manual_excluded),
            "probable_adsorbate_indices": probable_adsorbates,
            "probable_adsorbate_string": compress_index_ranges(probable_adsorbates),
            "unmatched_reference_indices": unmatched_reference_indices,
            "unmatched_reference_string": compress_index_ranges(unmatched_reference_indices),
            "z_min_slab": z_min,
            "z_max_slab": z_max,
            "z_threshold": z_threshold,
            "fixed_reference_indices": fixed_reference_indices,
            "fixed_reference_string": compress_index_ranges(fixed_reference_indices),
            "fixed_atom_count": 0 if errors else len(fixed_indices),
            "fixed_atom_string": "" if errors else fixed_atom_string,
        },
    }
