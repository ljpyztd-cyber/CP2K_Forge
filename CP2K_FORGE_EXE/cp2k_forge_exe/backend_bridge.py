from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


TASK_OPTIONS = [
    ("ENERGY", "ENERGY"),
    ("GEO_OPT", "GEO_OPT"),
    ("CELL_OPT", "CELL_OPT"),
    ("MD", "MD (developing)"),
    ("BAND", "BAND (developing)"),
]

MODEL_SIZE_OPTIONS = [
    ("SMALL", "Small / BFGS"),
    ("LARGE", "Large / LBFGS"),
]

PERIODIC_OPTIONS = [("XYZ", "XYZ"), ("XY", "XY"), ("XZ", "XZ"), ("YZ", "YZ"), ("X", "X"), ("Y", "Y"), ("Z", "Z"), ("NONE", "NONE")]

FUNCTIONAL_OPTIONS = [
    ("PBE", "PBE"),
    ("PBEsol", "PBEsol"),
    ("revPBE", "revPBE"),
    ("BLYP", "BLYP"),
    ("BP86", "BP86"),
    ("TPSS", "TPSS"),
    ("SCAN", "SCAN"),
    ("r2SCAN", "r2SCAN"),
    ("PBE0", "PBE0"),
    ("PBE0-ADMM", "PBE0-ADMM"),
    ("HSE06", "HSE06"),
    ("HSE06-ADMM", "HSE06-ADMM"),
    ("B3LYP", "B3LYP"),
    ("B3LYP-ADMM", "B3LYP-ADMM"),
    ("BEEF-vdW", "BEEF-vdW"),
]

BASIS_SET_OPTIONS = [
    ("DZVP-MOLOPT-SR-GTH", "DZVP-MOLOPT-SR-GTH"),
    ("SZV-MOLOPT-SR-GTH", "SZV-MOLOPT-SR-GTH"),
    ("TZVP-MOLOPT-GTH", "TZVP-MOLOPT-GTH"),
    ("TZV2P-MOLOPT-GTH", "TZV2P-MOLOPT-GTH"),
    ("TZV2PX-MOLOPT-GTH", "TZV2PX-MOLOPT-GTH"),
    ("DZVP-GTH", "DZVP-GTH"),
    ("TZVP-GTH", "TZVP-GTH"),
    ("6-31G*", "6-31G*"),
    ("6-311G**", "6-311G**"),
    ("Ahlrichs-def2-TZVP", "Ahlrichs-def2-TZVP"),
    ("pob-TZVP", "pob-TZVP"),
    ("pob-DZVP-rev2", "pob-DZVP-rev2"),
    ("pob-TZVP-rev2", "pob-TZVP-rev2"),
    ("Ahlrichs-def2-QZVP", "Ahlrichs-def2-QZVP"),
    ("def2-QZVP with RI_5Z", "def2-QZVP with RI_5Z"),
]

DISPERSION_OPTIONS = [
    ("DFTD3(BJ)", "DFTD3(BJ)"),
    ("DFTD3", "DFTD3"),
    ("DFTD4", "DFTD4"),
    ("rVV10", "rVV10"),
    ("None", "None"),
]

SCF_METHOD_OPTIONS = [("OT", "OT"), ("DIAG", "Diagonalization")]
SCF_ACCURACY_OPTIONS = [("Ultrafine", "Ultrafine"), ("Fine", "Fine"), ("Medium", "Medium"), ("Low", "Low"), ("Acceptable", "Acceptable")]
SCF_ACCURACY_VALUES = {
    "Ultrafine": "1.0E-07",
    "Fine": "1.0E-06",
    "Medium": "5.0E-06",
    "Low": "1.0E-05",
    "Acceptable": "3.0E-05",
}
MIXING_OPTIONS = [("Broyden", "Broyden"), ("Pulay", "Pulay")]
KPOINT_MODE_OPTIONS = [("GAMMA", "GAMMA"), ("MONKHORST_PACK", "MONKHORST_PACK")]
OT_MINIMIZER_OPTIONS = [("DIIS", "DIIS"), ("CG", "CG")]

CHARGE_PRINT_OPTIONS = [
    ("None", "None"),
    ("Mulliken", "Mulliken"),
    ("Lowdin", "Lowdin"),
    ("Hirshfeld", "Hirshfeld"),
    ("Hirshfeld-I", "Hirshfeld-I"),
    ("Voronoi", "Voronoi"),
    ("RESP", "RESP"),
    ("REPEAT", "REPEAT"),
]

CUBE_PRINT_OPTIONS = [
    ("None", "None"),
    ("Electron density", "Electron density"),
    ("Density + Hartree", "Density + Hartree"),
    ("HOMO/LUMO only", "HOMO/LUMO only"),
    ("Molecular orbitals", "Molecular orbitals"),
    ("ELF", "ELF"),
    ("Hartree potential", "Hartree potential"),
    ("XC potential", "XC potential"),
    ("Electric field", "Electric field"),
]

FIXED_ATOM_MODE_OPTIONS = [("MANUAL", "Manual indices"), ("AUTO_BOTTOM", "Auto bottom z-range")]
SLURM_TEMPLATE_OPTIONS = [("local", "Non-SSH local"), ("ssh", "SSH CP2K 2026.1")]
SLURM_PRESET_OPTIONS = [
    ("general_64_4", "General 64 cores / 4 nodes"),
    ("small_32_1", "Small 32 cores / 1 node"),
    ("memory_saving", "Large memory saver"),
]
SLURM_CORES_PER_NODE_MODE_OPTIONS = [("default", "Default"), ("custom", "Custom")]
SLURM_PRESET_DEFAULTS = {
    "general_64_4": {"nodes": "4", "cores": "64", "coresPerNode": "16"},
    "small_32_1": {"nodes": "1", "cores": "32", "coresPerNode": "32"},
    "memory_saving": {"nodes": "16", "cores": "128", "coresPerNode": "8"},
}
SSH_SLURM_DEFAULTS = {"nodes": "1", "cores": "32", "coresPerNode": "32"}
DIAG_MAX_SCF_DEFAULTS = {"ENERGY": "1000", "GEO_OPT": "200", "CELL_OPT": "200"}


def ensure_backend_path() -> Path:
    backend_root = Path(__file__).resolve().parents[1]
    if backend_root.is_dir() and str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    return backend_root


@lru_cache(maxsize=1)
def _backend_module():
    ensure_backend_path()
    return importlib.import_module("cp2k_forge_backend.generation")


@lru_cache(maxsize=1)
def _rules_module():
    ensure_backend_path()
    return importlib.import_module("cp2k_forge_backend.rules")


def backend_default_values() -> dict[str, Any]:
    return dict(_backend_module().DEFAULT_VALUES)


def magnetic_moment_presets() -> dict[str, str]:
    return dict(_rules_module().MAGNETIC_MOMENT_PRESETS)


def dft_u_presets() -> dict[str, str]:
    return dict(_rules_module().DFT_U_PRESETS)


def generate_job(payload: dict[str, Any]) -> dict[str, Any]:
    return _backend_module().generate_job(payload)


def batch_generate_jobs(payload: dict[str, Any]) -> dict[str, Any]:
    return _backend_module().batch_generate_jobs(payload)


def prepare_auto_fixed_preview(payload: dict[str, Any]) -> dict[str, Any]:
    return _backend_module().prepare_auto_fixed_preview(payload)


def is_optimization_task(task: str) -> bool:
    return str(task or "").upper() in {"GEO_OPT", "CELL_OPT"}


def current_slurm_defaults(template: str, preset: str) -> dict[str, str]:
    if str(template or "local").lower() == "ssh":
        return dict(SSH_SLURM_DEFAULTS)
    return dict(SLURM_PRESET_DEFAULTS.get(preset, SLURM_PRESET_DEFAULTS["general_64_4"]))


def default_cores_per_node(template: str, preset: str, nodes_value: str, cores_value: str) -> str:
    defaults = current_slurm_defaults(template, preset)
    try:
        nodes = max(1, int(str(nodes_value or defaults["nodes"]).strip()))
    except ValueError:
        nodes = int(defaults["nodes"])
    try:
        cores = max(1, int(str(cores_value or defaults["cores"]).strip()))
    except ValueError:
        cores = int(defaults["cores"])
    if nodes <= 0:
        return defaults["coresPerNode"]
    if cores % nodes == 0:
        return str(max(1, cores // nodes))
    return str(max(1, (cores + nodes - 1) // nodes))


def diag_max_scf_default(task: str) -> str:
    return DIAG_MAX_SCF_DEFAULTS.get(str(task or "").upper(), DIAG_MAX_SCF_DEFAULTS["ENERGY"])


def scf_accuracy_eps(value: str) -> str:
    return SCF_ACCURACY_VALUES.get(str(value or "Medium"), SCF_ACCURACY_VALUES["Medium"])
