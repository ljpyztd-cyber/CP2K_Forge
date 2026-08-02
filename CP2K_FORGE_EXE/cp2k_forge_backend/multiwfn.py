from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]

FALLBACK_MULTIWFN_EXE = Path(
    r"D:\Multiwfn\Multiwfn_3.8_dev_bin_Win64\Multiwfn_3.8_dev_bin_Win64\Multiwfn.exe"
)


def _bundled_multiwfn_candidates() -> list[Path]:
    project_root = APP_ROOT.parent
    return [
        APP_ROOT / "Multiwfn" / "Multiwfn.exe",
        APP_ROOT / "Multiwfn.exe",
        APP_ROOT / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
        APP_ROOT / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
        APP_ROOT / "tools" / "Multiwfn" / "Multiwfn.exe",
        APP_ROOT / "tools" / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
        APP_ROOT / "tools" / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
        project_root / "Multiwfn" / "Multiwfn.exe",
        project_root / "Multiwfn.exe",
        project_root / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
        project_root / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn_3.8_dev_bin_Win64" / "Multiwfn.exe",
    ]


def find_bundled_multiwfn_exe() -> Path | None:
    for candidate in _bundled_multiwfn_candidates():
        if candidate.is_file():
            return candidate
    return None


def resolve_multiwfn_exe(value: Any = "") -> Path:
    text = str(value or "").strip().strip('"')
    if text:
        candidate = Path(text)
        if candidate.is_dir():
            exe_in_dir = candidate / "Multiwfn.exe"
            if exe_in_dir.is_file():
                return exe_in_dir
        if candidate.is_file():
            return candidate
    return find_bundled_multiwfn_exe() or FALLBACK_MULTIWFN_EXE


DEFAULT_MULTIWFN_EXE = resolve_multiwfn_exe()

FUNCTIONAL_CODES = {
    "LDA/PADE": "1",
    "PBE": "2",
    "revPBE": "-2",
    "PBEsol": "-3",
    "TPSS": "3",
    "BP86": "4",
    "BLYP": "5",
    "PBE0": "6",
    "PBE0-ADMM": "-6",
    "B3LYP": "7",
    "B3LYP-ADMM": "-7",
    "HSE06": "8",
    "HSE06-ADMM": "-8",
    "BHandHLYP": "9",
    "SCAN": "13",
    "r2SCAN": "14",
    "BEEF-vdW": "17",
}

BASIS_CODES = {
    "SZV-MOLOPT-SR-GTH": "1",
    "DZVP-MOLOPT-SR-GTH": "2",
    "TZVP-MOLOPT-GTH": "3",
    "TZV2P-MOLOPT-GTH": "4",
    "TZV2PX-MOLOPT-GTH": "5",
    "SZV-GTH": "-1",
    "DZVP-GTH": "-2",
    "TZVP-GTH": "-3",
    "TZV2P-GTH": "-4",
    "QZV2P-GTH": "-5",
    "QZV3P-GTH": "-6",
    "6-31G*": "10",
    "6-311G**": "11",
    "Ahlrichs-def2-TZVP": "12",
    "pob-TZVP": "13",
    "pob-DZVP-rev2": "14",
    "pob-TZVP-rev2": "15",
    "Ahlrichs-def2-QZVP": "16",
    "def2-QZVP with RI_5Z": "19",
}

TASK_CODES = {
    "ENERGY": "1",
    "ENERGY_FORCE": "2",
    "GEO_OPT": "3",
    "CELL_OPT": "4",
    "VIBRATIONAL_ANALYSIS": "5",
    "MD": "6",
    "BAND": "8",
}

GEOMETRY_OPTIMIZER_CODES = {
    "BFGS": "1",
    "LBFGS": "2",
    "CG": "3",
}

DISPERSION_CODES = {
    "None": "0",
    "DFTD3": "1",
    "DFTD3(BJ)": "2",
    "DFTD4": "3",
    "rVV10": "5",
}

MIXING_CODES = {
    "Broyden": "2",
    "Pulay": "3",
}

CHARGE_PRINT_CODES = {
    "None": "0",
    "Mulliken": "1",
    "Lowdin": "2",
    "Hirshfeld": "3",
    "Hirshfeld-I": "4",
    "Voronoi": "5",
    "RESP": "6",
    "REPEAT": "7",
}

POISSON_CODES = {
    "PERIODIC": "1",
    "ANALYTIC": "2",
    "WAVELET": "4",
}

CUBE_PRINT_CODES = {
    "None": "0",
    "HOMO/LUMO only": "-1",
    "Electron density": "1",
    "ELF": "2",
    "XC potential": "3",
    "Hartree potential": "4",
    "Electric field": "5",
    "Molecular orbitals": "6",
    "Density + Hartree": "7",
}


@dataclass
class MultiwfnResult:
    ok: bool
    log: str
    command_script: str
    output_path: Path
    returncode: int | None = None
    error: str | None = None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _multiwfn_atom_index_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("；", ",").replace("，", ",").replace(";", ",")
    text = ",".join(part for part in text.replace("\n", " ").split() if part)
    text = ",".join(part for part in text.split(",") if part.strip())
    return text


def _cif_requires_occupancy_confirmation(input_path: Path) -> bool:
    """Return whether Multiwfn will pause after loading a partial-occupancy CIF."""
    if input_path.suffix.lower() not in {".cif", ".mcif"}:
        return False

    try:
        lines = input_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False

    number_pattern = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?")
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "loop_":
            index += 1
            continue

        index += 1
        headers: list[str] = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                continue
            if not stripped.startswith("_"):
                break
            headers.append(stripped.split(maxsplit=1)[0].lower())
            index += 1

        try:
            occupancy_index = headers.index("_atom_site_occupancy")
        except ValueError:
            continue

        pending_tokens: list[str] = []
        while index < len(lines):
            stripped = lines[index].strip()
            lowered = stripped.lower()
            if lowered == "loop_" or lowered.startswith(("data_", "save_", "stop_")):
                break
            if stripped.startswith("_"):
                break
            index += 1
            if not stripped or stripped.startswith("#"):
                continue
            try:
                pending_tokens.extend(shlex.split(stripped, comments=True, posix=True))
            except ValueError:
                continue

            while len(pending_tokens) >= len(headers):
                row = pending_tokens[: len(headers)]
                del pending_tokens[: len(headers)]
                occupancy_text = row[occupancy_index]
                if occupancy_text in {".", "?"}:
                    continue
                match = number_pattern.match(occupancy_text)
                if match and float(match.group(0)) < 1.0 - 1.0e-9:
                    return True

    return False


def _multiwfn_input_commands(input_path: Path) -> list[str]:
    commands = [str(input_path)]
    if _cif_requires_occupancy_confirmation(input_path):
        commands.append("")
    return commands


def build_multiwfn_commands(input_path: Path, output_path: Path, values: dict[str, Any]) -> list[str]:
    commands = [*_multiwfn_input_commands(input_path), "cp2k", str(output_path)]

    periodic = str(values.get("periodic", "XYZ")).strip().upper()
    if periodic:
        commands.extend(["-7", periodic])

    task = str(values.get("task", "ENERGY"))
    task_code = TASK_CODES.get(task, "1")
    if task_code != "1":
        commands.extend(["-1", task_code])
    if task in {"GEO_OPT", "CELL_OPT"}:
        optimizer = str(values.get("geo_optimizer", "BFGS")).strip().upper()
        optimizer_code = GEOMETRY_OPTIMIZER_CODES.get(optimizer)
        if optimizer_code:
            commands.extend(["10", optimizer_code])
        fixed_atoms = _multiwfn_atom_index_text(values.get("fixed_atoms", ""))
        if fixed_atoms:
            commands.extend(["9", fixed_atoms])

    functional = str(values.get("functional", "PBE"))
    functional_code = FUNCTIONAL_CODES.get(functional)
    if functional_code and functional != "PBE":
        commands.extend(["1", functional_code])

    basis = str(values.get("basis_set", "DZVP-MOLOPT-SR-GTH"))
    basis_code = BASIS_CODES.get(basis)
    if basis_code and basis != "DZVP-MOLOPT-SR-GTH":
        commands.extend(["2", basis_code])

    dispersion = str(values.get("dispersion", "DFTD3(BJ)"))
    dispersion_code = DISPERSION_CODES.get(dispersion)
    if dispersion_code is not None:
        commands.extend(["3", dispersion_code])

    if values.get("scf_method") == "OT":
        commands.append("4")
    else:
        mixing = str(values.get("mixing", "Broyden"))
        if mixing in MIXING_CODES and mixing != "Broyden":
            commands.extend(["5", MIXING_CODES[mixing]])
        if _truthy(values.get("smearing", False)):
            commands.append("6")

    if str(values.get("charge_print", "None")) != "None":
        commands.extend(["-4", CHARGE_PRINT_CODES.get(str(values.get("charge_print")), "0")])

    if _truthy(values.get("molden_print", values.get("output_molden", False))):
        commands.append("-2")

    cube_print = str(values.get("cube_print", "None"))
    if cube_print != "None":
        commands.extend(["-3", CUBE_PRINT_CODES.get(cube_print, "0")])

    kpoints_mode = str(values.get("kpoints_mode", "GAMMA"))
    if kpoints_mode != "GAMMA":
        commands.extend(["8", str(values.get("kpoints", "1,1,1")).replace(" ", "")])

    other: list[str] = []
    if str(values.get("charge", "0")).strip() != "0":
        other.extend(["1", str(values.get("charge", "0")).strip()])
    multiplicity = str(values.get("multiplicity", "AUTO")).strip()
    if multiplicity.upper() not in {"", "AUTO", "DEFAULT", "0", "1"}:
        other.extend(["2", multiplicity])

    cutoff = str(values.get("cutoff", "400")).strip()
    rel_cutoff = str(values.get("rel_cutoff", "55")).strip()
    if cutoff or rel_cutoff:
        other.extend(["5", f"{cutoff},{rel_cutoff}"])

    poisson = str(values.get("poisson_solver", "AUTO"))
    if poisson in POISSON_CODES:
        other.extend(["22", POISSON_CODES[poisson]])

    if str(values.get("scf_method", "")).strip().upper() == "DIAG" and _truthy(values.get("add_mos_for_pdos", False)):
        added_mos = str(values.get("added_mos", "30")).strip() or "30"
        if added_mos == "0":
            added_mos = "30"
        other.extend(["12", added_mos])

    if other:
        commands.extend(["-9", *other, "0"])

    commands.extend(["0", "q"])
    return commands


def build_multiwfn_100_2_gjf_commands(input_path: Path, output_path: Path) -> list[str]:
    return [*_multiwfn_input_commands(input_path), "100", "2", "10", str(output_path), "q"]


def run_multiwfn(
    multiwfn_exe: Path,
    input_path: Path,
    output_path: Path,
    values: dict[str, Any],
    timeout: int = 120,
) -> MultiwfnResult:
    commands = build_multiwfn_commands(input_path, output_path, values)
    command_script = "\n".join(commands) + "\n"

    if not multiwfn_exe.is_file():
        return MultiwfnResult(
            ok=False,
            log="",
            command_script=command_script,
            output_path=output_path,
            error=f"Multiwfn executable not found: {multiwfn_exe}",
        )

    try:
        completed = subprocess.run(
            [str(multiwfn_exe)],
            input=command_script,
            cwd=str(output_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return MultiwfnResult(
            ok=False,
            log=log,
            command_script=command_script,
            output_path=output_path,
            error=f"Multiwfn timed out after {timeout} seconds.",
        )

    log = (completed.stdout or "") + "\n" + (completed.stderr or "")
    ok = output_path.is_file()
    error = None if ok else "Multiwfn did not create the expected CP2K input file."
    return MultiwfnResult(
        ok=ok,
        log=log,
        command_script=command_script,
        output_path=output_path,
        returncode=completed.returncode,
        error=error,
    )


def run_multiwfn_100_2_gjf(
    multiwfn_exe: Path,
    input_path: Path,
    output_path: Path,
    timeout: int = 120,
) -> MultiwfnResult:
    commands = build_multiwfn_100_2_gjf_commands(input_path, output_path)
    command_script = "\n".join(commands) + "\n"

    if not multiwfn_exe.is_file():
        return MultiwfnResult(
            ok=False,
            log="",
            command_script=command_script,
            output_path=output_path,
            error=f"Multiwfn executable not found: {multiwfn_exe}",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [str(multiwfn_exe)],
            input=command_script,
            cwd=str(output_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return MultiwfnResult(
            ok=False,
            log=log,
            command_script=command_script,
            output_path=output_path,
            error=f"Multiwfn 100-2 GJF export timed out after {timeout} seconds.",
        )

    log = (completed.stdout or "") + "\n" + (completed.stderr or "")
    ok = output_path.is_file()
    error = None if ok else "Multiwfn 100-2 did not create the expected GJF file."
    return MultiwfnResult(
        ok=ok,
        log=log,
        command_script=command_script,
        output_path=output_path,
        returncode=completed.returncode,
        error=error,
    )
