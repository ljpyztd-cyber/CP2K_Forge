from __future__ import annotations

import math
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


ELEMENTS = [
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
ATOMIC_NUMBERS = {symbol: index + 1 for index, symbol in enumerate(ELEMENTS)}
SYMBOL_BY_NUMBER = {number: symbol for symbol, number in ATOMIC_NUMBERS.items()}

ATOM_COLORS = {
    "H": "#FFFFFF", "He": "#D8FFFF", "Li": "#CC7CFF", "Be": "#CCFF00",
    "B": "#FFB4B4", "C": "#8E8E8E", "N": "#1818E4", "O": "#E40000",
    "F": "#B1FFFF", "Ne": "#AFE2F4", "Na": "#AA5BF1", "Mg": "#B1CC00",
    "Al": "#D0A5A5", "Si": "#7E9999", "P": "#FF7E00", "S": "#FFC628",
    "Cl": "#18EF18", "Ar": "#7ED0E2", "K": "#8E3FD3", "Ca": "#999900",
    "Sc": "#E4E4E2", "Ti": "#BEC1C6", "V": "#A5A5AA", "Cr": "#8999C6",
    "Mn": "#9A79C6", "Fe": "#7E79C6", "Co": "#5B6DFF", "Ni": "#5B79C1",
    "Cu": "#FF7960", "Zn": "#7C7EAF", "Ga": "#C18E8E", "Ge": "#668E8E",
    "As": "#BC7EE2", "Se": "#FFA000", "Br": "#A52020", "Kr": "#5BB9D0",
    "Rb": "#6F2DAF", "Sr": "#7E6600", "Y": "#93FBFF", "Zr": "#93DFDF",
    "Nb": "#72C1C8", "Mo": "#53B4B4", "Tc": "#3A9DA7", "Ru": "#238E95",
    "Rh": "#097C8B", "Pd": "#006783", "Ag": "#99C6FF", "Cd": "#FFD88E",
    "In": "#A57472", "Sn": "#667E7E", "Sb": "#9D62B4", "Te": "#D37900",
    "I": "#930093", "Xe": "#419DAF", "Cs": "#56168E", "Ba": "#663300",
    "La": "#6FDDFF", "Ce": "#FFFFC6", "Pr": "#D8FFC6", "Nd": "#C6FFC6",
    "Pm": "#A2FFC6", "Sm": "#8EFFC6", "Eu": "#60FFC6", "Gd": "#44FFC6",
    "Tb": "#2FFFC6", "Dy": "#1DFFB4", "Ho": "#00FFB4", "Er": "#00E474",
    "Tm": "#00D350", "Yb": "#00BE37", "Lu": "#00AA23", "Hf": "#4BC1FF",
    "Ta": "#4BA5FF", "W": "#2593D5", "Re": "#257CAA", "Os": "#256695",
    "Ir": "#165386", "Pt": "#165B8E", "Au": "#FFD023", "Hg": "#B4B4C1",
    "Tl": "#A5534B", "Pb": "#565860", "Bi": "#9D4EB4", "Po": "#AA5B00",
    "At": "#744E44", "Rn": "#418195", "Fr": "#410066", "Ra": "#4B1800",
    "Ac": "#6FAAF9", "Th": "#00B9FF", "Pa": "#00A0FF", "U": "#008EFF",
    "Np": "#007EF1", "Pu": "#006AF1", "Am": "#535BF1", "Cm": "#775BE2",
    "Bk": "#895DE2", "Cf": "#A034D3", "Es": "#A72AC6", "Fm": "#B11DB9",
    "Md": "#B10CA5", "No": "#BC0C86", "Lr": "#C60066", "Rf": "#FF7E7E",
    "Db": "#E46666", "Sg": "#CC4B4B", "Bh": "#B13333", "Hs": "#991818",
    "Mt": "#8B0000", "Ds": "#7E0000", "Rg": "#720000",
}

ATOM_RADII = {
    "H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57,
    "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07,
    "S": 1.05, "Cl": 1.02, "K": 2.03, "Ca": 1.76, "Ti": 1.60,
    "V": 1.53, "Cr": 1.39, "Mn": 1.39, "Fe": 1.32, "Co": 1.26,
    "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Br": 1.20, "Mo": 1.54,
    "Ag": 1.45, "I": 1.39, "W": 1.62, "Pt": 1.36, "Au": 1.36,
    "Pb": 1.46, "Ce": 2.04, "U": 1.96,
}

VDW_RADII = {
    "H": 1.20, "He": 1.40, "Li": 1.82, "Be": 1.53, "B": 1.92,
    "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "Ne": 1.54,
    "Na": 2.27, "Mg": 1.73, "Al": 1.84, "Si": 2.10, "P": 1.80,
    "S": 1.80, "Cl": 1.75, "Ar": 1.88, "K": 2.75, "Ca": 2.31,
    "Sc": 2.30, "Ti": 2.15, "V": 2.05, "Cr": 2.05, "Mn": 2.05,
    "Fe": 2.05, "Co": 2.00, "Ni": 2.00, "Cu": 2.00, "Zn": 2.10,
    "Ga": 1.87, "Ge": 2.11, "As": 1.85, "Se": 1.90, "Br": 1.85,
    "Kr": 2.02, "Rb": 3.03, "Sr": 2.49, "Y": 2.40, "Zr": 2.30,
    "Nb": 2.15, "Mo": 2.10, "Tc": 2.05, "Ru": 2.05, "Rh": 2.00,
    "Pd": 2.05, "Ag": 2.10, "Cd": 2.20, "In": 2.20, "Sn": 2.25,
    "Sb": 2.20, "Te": 2.06, "I": 1.98, "Xe": 2.16, "Cs": 3.43,
    "Ba": 2.68, "La": 2.50, "Ce": 2.48, "Pr": 2.47, "Nd": 2.45,
    "Pm": 2.43, "Sm": 2.42, "Eu": 2.40, "Gd": 2.38, "Tb": 2.37,
    "Dy": 2.35, "Ho": 2.33, "Er": 2.32, "Tm": 2.30, "Yb": 2.28,
    "Lu": 2.27, "Hf": 2.25, "Ta": 2.20, "W": 2.10, "Re": 2.05,
    "Os": 2.00, "Ir": 2.00, "Pt": 2.05, "Au": 2.10, "Hg": 2.05,
    "Tl": 1.96, "Pb": 2.02, "Bi": 2.07, "Po": 1.97, "At": 2.02,
    "Rn": 2.20, "Fr": 3.48, "Ra": 2.83, "Ac": 2.00, "Th": 2.40,
    "Pa": 2.00, "U": 1.86, "Np": 2.00, "Pu": 2.00, "Am": 2.00,
    "Cm": 2.00, "Bk": 2.00, "Cf": 2.00, "Es": 2.00, "Fm": 2.00,
    "Md": 2.00, "No": 2.00, "Lr": 2.00,
}


@dataclass(frozen=True)
class Atom:
    index: int
    symbol: str
    atomic_number: int
    x: float
    y: float
    z: float


@dataclass
class Molecule:
    atoms: list[Atom]
    bonds: list[tuple[int, int]]
    source_path: str = ""
    visual_source_path: str = ""
    cell_vectors: tuple[tuple[float, float, float], ...] | None = None
    warnings: list[str] | None = None


STRUCTURE_CONVERSION_FORMATS = {
    "cif": {"menu": "33", "suffix": ".cif"},
    "xyz": {"menu": "2", "suffix": ".xyz"},
    "pdb": {"menu": "1", "suffix": ".pdb"},
    "gjf": {"menu": "10", "suffix": ".gjf"},
    "gro": {"menu": "34", "suffix": ".gro"},
    "poscar": {"menu": "27", "suffix": ".poscar"},
}


def normalize_symbol(token: str) -> str | None:
    value = str(token or "").strip().strip("'\"")
    if not value:
        return None
    if value.isdigit():
        return SYMBOL_BY_NUMBER.get(int(value))
    match = re.match(r"([A-Za-z]{1,2})", value)
    if not match:
        return None
    symbol = match.group(1)
    symbol = symbol[0].upper() + symbol[1:].lower()
    return symbol if symbol in ATOMIC_NUMBERS else None


def parse_atom_indices(text: str) -> set[int]:
    atoms: set[int] = set()
    for part in re.split(r"[,; \t\r\n]+", str(text or "").strip()):
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a, b = int(left), int(right)
            except ValueError:
                continue
            if a > b:
                a, b = b, a
            atoms.update(range(a, b + 1))
        else:
            try:
                atoms.add(int(part))
            except ValueError:
                continue
    return atoms


def atoms_to_range_text(indices: set[int] | list[int]) -> str:
    values = sorted({int(i) for i in indices if int(i) > 0})
    if not values:
        return ""
    ranges: list[str] = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = value
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(ranges)


def _float_token(value: str) -> float | None:
    clean = re.sub(r"\([^)]*\)$", "", str(value).strip())
    try:
        return float(clean)
    except ValueError:
        return None


def _atom_from_parts(index: int, parts: list[str]) -> Atom | None:
    if len(parts) < 4:
        return None
    symbol = normalize_symbol(parts[0])
    if not symbol:
        return None
    nums = [_float_token(p) for p in parts[1:4]]
    if any(v is None for v in nums):
        return None
    return Atom(index=index, symbol=symbol, atomic_number=ATOMIC_NUMBERS[symbol], x=nums[0], y=nums[1], z=nums[2])


def parse_xyz(text: str) -> list[Atom]:
    lines = text.splitlines()
    start = 2 if lines and lines[0].strip().isdigit() else 0
    atoms: list[Atom] = []
    for line in lines[start:]:
        parts = line.split()
        atom = _atom_from_parts(len(atoms) + 1, parts)
        if atom:
            atoms.append(atom)
    return atoms


def parse_pdb(text: str) -> list[Atom]:
    atoms: list[Atom] = []
    for line in text.splitlines():
        if line.startswith("ENDMDL") and atoms:
            break
        if not line.startswith(("ATOM", "HETATM")):
            continue
        alt_location = line[16:17].strip() if len(line) > 16 else ""
        if alt_location not in {"", "A", "1"}:
            continue
        symbol = line[76:78].strip() if len(line) >= 78 else ""
        if not symbol:
            atom_name = line[12:16] if len(line) >= 16 else ""
            letters = re.sub(r"[^A-Za-z]", "", atom_name)
            if atom_name[:1].isspace() or line.startswith("ATOM"):
                symbol = letters[:1]
            else:
                symbol = letters[:2]
        symbol = normalize_symbol(symbol)
        if not symbol:
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        atoms.append(Atom(len(atoms) + 1, symbol, ATOMIC_NUMBERS[symbol], x, y, z))
    return atoms


def parse_pdb_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    for line in text.splitlines():
        if not line.startswith("CRYST1"):
            continue
        try:
            a = float(line[6:15])
            b = float(line[15:24])
            c = float(line[24:33])
            alpha = float(line[33:40])
            beta = float(line[40:47])
            gamma = float(line[47:54])
        except ValueError:
            parts = line.split()
            if len(parts) < 7:
                return None
            try:
                a, b, c, alpha, beta, gamma = map(float, parts[1:7])
            except ValueError:
                return None
        if min(a, b, c) <= 0:
            return None
        return _cell_vectors(a, b, c, alpha, beta, gamma)
    return None


def parse_gro(text: str) -> list[Atom]:
    lines = text.splitlines()
    if len(lines) < 3:
        return []
    try:
        atom_count = int(lines[1].strip())
    except ValueError:
        return []
    atoms: list[Atom] = []
    for line in lines[2:2 + atom_count]:
        symbol_text = line[10:15].strip() if len(line) >= 15 else ""
        symbol = normalize_symbol(symbol_text)
        if not symbol:
            symbol = normalize_symbol(re.sub(r"[^A-Za-z]", "", symbol_text))
        if not symbol:
            continue
        try:
            if len(line) >= 44:
                x = float(line[20:28]) * 10.0
                y = float(line[28:36]) * 10.0
                z = float(line[36:44]) * 10.0
            else:
                parts = line.split()
                x, y, z = (float(parts[-3]) * 10.0, float(parts[-2]) * 10.0, float(parts[-1]) * 10.0)
        except (ValueError, IndexError):
            continue
        atoms.append(Atom(len(atoms) + 1, symbol, ATOMIC_NUMBERS[symbol], x, y, z))
    return atoms


def parse_gro_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return None
    try:
        values = [float(value) * 10.0 for value in lines[-1].split()]
    except ValueError:
        return None
    if len(values) == 3:
        return (values[0], 0.0, 0.0), (0.0, values[1], 0.0), (0.0, 0.0, values[2])
    if len(values) >= 9:
        return (
            (values[0], values[3], values[4]),
            (values[5], values[1], values[6]),
            (values[7], values[8], values[2]),
        )
    return None


def _scaled_vector(parts: list[str], scale: float) -> tuple[float, float, float] | None:
    if len(parts) < 3:
        return None
    values = [_float_token(part) for part in parts[:3]]
    if any(value is None for value in values):
        return None
    return (values[0] * scale, values[1] * scale, values[2] * scale)


def _frac_to_cart(frac: tuple[float, float, float], vectors: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    a, b, c = vectors
    return (
        frac[0] * a[0] + frac[1] * b[0] + frac[2] * c[0],
        frac[0] * a[1] + frac[1] * b[1] + frac[2] * c[1],
        frac[0] * a[2] + frac[1] * b[2] + frac[2] * c[2],
    )


def _parse_poscar_payload(text: str) -> tuple[list[Atom], tuple[tuple[float, float, float], ...] | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 8:
        return [], None
    scale = _float_token(lines[1].split()[0])
    if scale is None or scale == 0:
        scale = 1.0
    vectors_unscaled = [_scaled_vector(lines[index].split(), 1.0) for index in range(2, 5)]
    if any(vector is None for vector in vectors_unscaled):
        return [], None
    if scale < 0:
        a_raw, b_raw, c_raw = vectors_unscaled
        raw_volume = abs(
            a_raw[0] * (b_raw[1] * c_raw[2] - b_raw[2] * c_raw[1])
            - a_raw[1] * (b_raw[0] * c_raw[2] - b_raw[2] * c_raw[0])
            + a_raw[2] * (b_raw[0] * c_raw[1] - b_raw[1] * c_raw[0])
        )
        if raw_volume <= 1e-12:
            return [], None
        scale = (-scale / raw_volume) ** (1.0 / 3.0)
    vectors_raw = [tuple(component * scale for component in vector) for vector in vectors_unscaled]
    if any(vector is None for vector in vectors_raw):
        return [], None
    vectors = (vectors_raw[0], vectors_raw[1], vectors_raw[2])

    cursor = 5
    symbols = [normalize_symbol(part) for part in lines[cursor].split()]
    has_symbol_line = all(symbols) and bool(symbols)
    if has_symbol_line:
        cursor += 1
    else:
        symbols = []

    try:
        counts = [int(float(part)) for part in lines[cursor].split()]
    except ValueError:
        return [], vectors
    cursor += 1

    if cursor < len(lines) and lines[cursor].lower().startswith("s"):
        cursor += 1
    direct = True
    if cursor < len(lines):
        mode = lines[cursor].lower()
        direct = not mode.startswith(("c", "k"))
        cursor += 1

    expanded_symbols: list[str] = []
    if has_symbol_line:
        for symbol, count in zip(symbols, counts):
            expanded_symbols.extend([symbol] * count)
    else:
        for element_index, count in enumerate(counts, start=1):
            symbol = SYMBOL_BY_NUMBER.get(element_index, "X")
            expanded_symbols.extend([symbol] * count)

    atoms: list[Atom] = []
    for symbol in expanded_symbols:
        if cursor >= len(lines):
            break
        parts = lines[cursor].split()
        cursor += 1
        coords = [_float_token(part) for part in parts[:3]]
        if any(value is None for value in coords):
            continue
        if direct:
            x, y, z = _frac_to_cart((coords[0], coords[1], coords[2]), vectors)
        else:
            x, y, z = coords[0] * scale, coords[1] * scale, coords[2] * scale
        normalized = normalize_symbol(symbol)
        if not normalized:
            continue
        atoms.append(Atom(len(atoms) + 1, normalized, ATOMIC_NUMBERS[normalized], x, y, z))
    return atoms, vectors


def parse_poscar(text: str) -> list[Atom]:
    atoms, _vectors = _parse_poscar_payload(text)
    return atoms


def parse_poscar_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    _atoms, vectors = _parse_poscar_payload(text)
    return vectors


def parse_gjf(text: str) -> list[Atom]:
    atoms: list[Atom] = []
    in_coords = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_coords:
            if re.match(r"^-?\d+\s+\d+", stripped):
                in_coords = True
            continue
        if not stripped:
            if atoms:
                break
            continue
        parts = stripped.split()
        atom = _atom_from_parts(len(atoms) + 1, parts)
        if atom:
            atoms.append(atom)
    return atoms


def parse_gjf_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    vectors: list[tuple[float, float, float]] = []
    in_coords = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_coords:
            if re.match(r"^-?\d+\s+\d+", stripped):
                in_coords = True
            continue
        if not stripped:
            if vectors:
                break
            continue
        parts = stripped.split()
        if len(parts) >= 4 and parts[0].lower() == "tv":
            coords = [_float_token(part) for part in parts[1:4]]
            if all(value is not None for value in coords):
                vectors.append((coords[0], coords[1], coords[2]))
    return tuple(vectors[:3]) if len(vectors) >= 3 else None


def _cell_vectors(a: float, b: float, c: float, alpha: float, beta: float, gamma: float) -> tuple[tuple[float, float, float], ...]:
    ar, br, gr = math.radians(alpha), math.radians(beta), math.radians(gamma)
    ax, ay, az = a, 0.0, 0.0
    bx, by, bz = b * math.cos(gr), b * math.sin(gr), 0.0
    cx = c * math.cos(br)
    cy = c * (math.cos(ar) - math.cos(br) * math.cos(gr)) / max(math.sin(gr), 1e-8)
    cz_sq = max(c * c - cx * cx - cy * cy, 0.0)
    return (ax, ay, az), (bx, by, bz), (cx, cy, math.sqrt(cz_sq))


def parse_cif_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    lines = text.splitlines()
    cell = {"a": None, "b": None, "c": None, "alpha": 90.0, "beta": 90.0, "gamma": 90.0}
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0].lower()
        value = _float_token(parts[1])
        if value is None:
            continue
        if key == "_cell_length_a":
            cell["a"] = value
        elif key == "_cell_length_b":
            cell["b"] = value
        elif key == "_cell_length_c":
            cell["c"] = value
        elif key == "_cell_angle_alpha":
            cell["alpha"] = value
        elif key == "_cell_angle_beta":
            cell["beta"] = value
        elif key == "_cell_angle_gamma":
            cell["gamma"] = value
    if cell["a"] and cell["b"] and cell["c"]:
        return _cell_vectors(cell["a"], cell["b"], cell["c"], cell["alpha"], cell["beta"], cell["gamma"])
    return None


def parse_cif(text: str) -> list[Atom]:
    lines = text.splitlines()
    atoms: list[Atom] = []
    vectors = parse_cif_cell_vectors(text)

    i = 0
    while i < len(lines):
        if lines[i].strip().lower() != "loop_":
            i += 1
            continue
        i += 1
        headers: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("_"):
            headers.append(lines[i].strip())
            i += 1
        if not any(h.lower().startswith("_atom_site") for h in headers):
            continue
        names = [h.split(".")[-1].lower().replace("_atom_site_", "") for h in headers]
        symbol_idx = next((names.index(n) for n in ("type_symbol", "label") if n in names), None)
        fx_idx = names.index("fract_x") if "fract_x" in names else None
        fy_idx = names.index("fract_y") if "fract_y" in names else None
        fz_idx = names.index("fract_z") if "fract_z" in names else None
        cx_idx = names.index("cartn_x") if "cartn_x" in names else None
        cy_idx = names.index("cartn_y") if "cartn_y" in names else None
        cz_idx = names.index("cartn_z") if "cartn_z" in names else None
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith("#") or stripped.lower() == "loop_" or stripped.startswith("_"):
                break
            try:
                parts = shlex.split(stripped)
            except ValueError:
                parts = stripped.split()
            symbol = normalize_symbol(parts[symbol_idx]) if symbol_idx is not None and symbol_idx < len(parts) else None
            xyz = None
            if symbol and vectors and None not in (fx_idx, fy_idx, fz_idx) and max(fx_idx, fy_idx, fz_idx) < len(parts):
                frac_vals = (_float_token(parts[fx_idx]), _float_token(parts[fy_idx]), _float_token(parts[fz_idx]))
                if all(v is not None for v in frac_vals):
                    xyz = _frac_to_cart(frac_vals, vectors)
            elif symbol and None not in (cx_idx, cy_idx, cz_idx) and max(cx_idx, cy_idx, cz_idx) < len(parts):
                xyz_vals = (_float_token(parts[cx_idx]), _float_token(parts[cy_idx]), _float_token(parts[cz_idx]))
                if all(v is not None for v in xyz_vals):
                    xyz = xyz_vals
            if symbol and xyz:
                atoms.append(Atom(len(atoms) + 1, symbol, ATOMIC_NUMBERS[symbol], xyz[0], xyz[1], xyz[2]))
            i += 1
    return atoms


def parse_cp2k_coord(text: str) -> list[Atom]:
    has_coord_section = any(re.match(r"^\s*&COORD(?:\s|$)", line, re.IGNORECASE) for line in text.splitlines())
    if not has_coord_section:
        if any(line.lstrip().startswith("&") for line in text.splitlines()):
            return []
        return parse_fallback(text)

    atoms: list[Atom] = []
    in_coord = False
    for raw in text.splitlines():
        line = raw.split("!", 1)[0].split("#", 1)[0].strip()
        upper = line.upper()
        if not line:
            continue
        if upper.startswith("&COORD"):
            in_coord = True
            continue
        if in_coord and upper.startswith("&END"):
            break
        if not in_coord:
            continue
        atom = _atom_from_parts(len(atoms) + 1, line.split())
        if atom:
            atoms.append(atom)
    return atoms


def parse_cp2k_cell_vectors(text: str) -> tuple[tuple[float, float, float], ...] | None:
    vectors: dict[str, tuple[float, float, float]] = {}
    abc: tuple[float, float, float] | None = None
    angles = (90.0, 90.0, 90.0)
    in_cell = False
    for raw in text.splitlines():
        line = raw.split("!", 1)[0].split("#", 1)[0].strip()
        upper = line.upper()
        if re.match(r"^&CELL(?:\s|$)", upper):
            in_cell = True
            continue
        if in_cell and (upper.startswith("&END CELL") or upper == "&END"):
            break
        if not in_cell or not line or line.startswith("&"):
            continue
        parts = re.sub(r"\[[^]]+\]", " ", line).split()
        if not parts:
            continue
        key = parts[0].upper()
        values = [_float_token(value) for value in parts[1:]]
        numbers = [float(value) for value in values if value is not None]
        if key in {"A", "B", "C"} and len(numbers) >= 3:
            vectors[key] = (numbers[0], numbers[1], numbers[2])
        elif key == "ABC" and len(numbers) >= 3:
            abc = (numbers[0], numbers[1], numbers[2])
        elif key == "ALPHA_BETA_GAMMA" and len(numbers) >= 3:
            angles = (numbers[0], numbers[1], numbers[2])
    if all(key in vectors for key in ("A", "B", "C")):
        return vectors["A"], vectors["B"], vectors["C"]
    if abc and min(abc) > 0:
        return _cell_vectors(abc[0], abc[1], abc[2], angles[0], angles[1], angles[2])
    return None


def parse_fallback(text: str) -> list[Atom]:
    atoms: list[Atom] = []
    for line in text.splitlines():
        atom = _atom_from_parts(len(atoms) + 1, line.split())
        if atom:
            atoms.append(atom)
    return atoms


def spatial_candidate_pairs(
    points: list[tuple[float, float, float]],
    cutoff: float,
) -> Iterator[tuple[int, int]]:
    if cutoff <= 0 or len(points) < 2:
        return
    cell_size = float(cutoff)
    buckets: dict[tuple[int, int, int], list[int]] = {}
    point_cells: list[tuple[int, int, int]] = []
    for index, (x, y, z) in enumerate(points):
        cell = (math.floor(x / cell_size), math.floor(y / cell_size), math.floor(z / cell_size))
        point_cells.append(cell)
        buckets.setdefault(cell, []).append(index)
    for index, cell in enumerate(point_cells):
        candidates: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    candidates.extend(buckets.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()))
        for other in sorted(candidate for candidate in candidates if candidate > index):
            yield index, other


def infer_bonds(atoms: list[Atom]) -> list[tuple[int, int]]:
    bonds: list[tuple[int, int]] = []
    if len(atoms) < 2:
        return bonds
    radii = [VDW_RADII.get(atom.symbol, 1.8) for atom in atoms]
    max_cutoff = 1.2 * max(radii)
    points = [(atom.x, atom.y, atom.z) for atom in atoms]
    for i, j in spatial_candidate_pairs(points, max_cutoff):
        a1 = atoms[i]
        a2 = atoms[j]
        r1 = VDW_RADII.get(a1.symbol, 1.8)
        r2 = VDW_RADII.get(a2.symbol, 1.8)
        dist = math.dist(points[i], points[j])
        if 0.15 < dist < 0.6 * (r1 + r2):
            bonds.append((a1.index, a2.index))
    return bonds


def safe_viewer_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._")
    return stem or "structure"


def _unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Cannot choose a unique output path for {path}")


def convert_structure_with_multiwfn(
    source: str | Path,
    multiwfn_exe: str | Path,
    target_format: str,
    output_dir: str | Path | None = None,
) -> tuple[Path, list[str]]:
    source_path = Path(source).resolve()
    format_key = str(target_format or "").strip().lower()
    if format_key not in STRUCTURE_CONVERSION_FORMATS:
        raise ValueError(f"Unsupported Multiwfn conversion format: {target_format}")

    exe_path = Path(multiwfn_exe).resolve()
    target_dir = (Path(output_dir) if output_dir else source_path.parent).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    info = STRUCTURE_CONVERSION_FORMATS[format_key]
    output_path = _unique_output_path(target_dir / f"{safe_viewer_stem(source_path)}_converted{info['suffix']}")
    command_script = "\n".join([str(source_path), "100", "2", str(info["menu"]), str(output_path), "q", ""])
    completed = subprocess.run(
        [str(exe_path)],
        input=command_script,
        cwd=target_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    warnings: list[str] = []
    if not output_path.is_file():
        log_tail = (completed.stdout + "\n" + completed.stderr).strip()[-1200:]
        raise RuntimeError(f"Multiwfn 100-2 {format_key.upper()} conversion did not create {output_path}.\n{log_tail}")
    return output_path, warnings


def convert_structure_to_gjf_for_viewer(source: str | Path, multiwfn_exe: str | Path, output_dir: str | Path) -> tuple[Path, list[str]]:
    return convert_structure_with_multiwfn(source, multiwfn_exe, "gjf", output_dir)


def load_molecule(path: str | Path) -> Molecule:
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    suffix = source.suffix.lower()
    parsers = {
        ".xyz": parse_xyz,
        ".pdb": parse_pdb,
        ".ent": parse_pdb,
        ".gro": parse_gro,
        ".gjf": parse_gjf,
        ".com": parse_gjf,
        ".cif": parse_cif,
        ".mcif": parse_cif,
        ".poscar": parse_poscar,
        ".vasp": parse_poscar,
        ".inp": parse_cp2k_coord,
        ".restart": parse_cp2k_coord,
    }
    parser = parse_poscar if source.name.lower().startswith("poscar") else parsers.get(suffix, parse_fallback)
    atoms = parser(text)
    if not atoms and parser is not parse_fallback:
        atoms = parse_fallback(text)
    cell_vectors = None
    if suffix in {".gjf", ".com"}:
        cell_vectors = parse_gjf_cell_vectors(text)
    elif suffix in {".cif", ".mcif"}:
        cell_vectors = parse_cif_cell_vectors(text)
    elif suffix in {".pdb", ".ent"}:
        cell_vectors = parse_pdb_cell_vectors(text)
    elif suffix == ".gro":
        cell_vectors = parse_gro_cell_vectors(text)
    elif suffix in {".poscar", ".vasp"} or source.name.lower().startswith("poscar"):
        cell_vectors = parse_poscar_cell_vectors(text)
    elif suffix in {".inp", ".restart"}:
        cell_vectors = parse_cp2k_cell_vectors(text)
    warnings: list[str] = []
    if not atoms:
        warnings.append("No atoms could be parsed from the structure file.")
    return Molecule(atoms=atoms, bonds=infer_bonds(atoms), source_path=str(source), visual_source_path=str(source), cell_vectors=cell_vectors, warnings=warnings)
