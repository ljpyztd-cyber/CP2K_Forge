from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from . import __version__
from .local_slurm import DEFAULT_SLURM_SCRIPT_NAME, render_local_cp2k_slurm, safe_slurm_script_name
from .multiwfn import DEFAULT_MULTIWFN_EXE, resolve_multiwfn_exe, run_multiwfn, run_multiwfn_100_2_gjf
from .patcher import apply_cp2k_forge_patches
from .rules import RuleMessage, detect_element_counts, normalize_spec
from .structure_table import (
    parse_gjf_atom_table,
    select_freeze_bottom_z_range,
    select_freeze_bottom_z_range_from_reference,
)


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = APP_ROOT / "workspace"
JOBS_DIR = WORKSPACE_DIR / "jobs"
GJF_SUFFIXES = {".gjf", ".com"}


DEFAULT_VALUES: dict[str, Any] = {
    "multiwfn_exe": str(DEFAULT_MULTIWFN_EXE.parent),
    "source_path": "",
    "project": "cp2k_job",
    "task": "ENERGY",
    "model_size": "SMALL",
    "periodic": "XYZ",
    "poisson_solver": "AUTO",
    "functional": "PBE",
    "basis_set": "DZVP-MOLOPT-SR-GTH",
    "dispersion": "DFTD3(BJ)",
    "scf_method": "OT",
    "mixing": "Broyden",
    "ot_minimizer": "DIIS",
    "smearing": False,
    "electronic_temperature": "300",
    "scf_accuracy": "Medium",
    "add_mos_for_pdos": False,
    "added_mos": "0",
    "kpoints_mode": "GAMMA",
    "kpoints": "1,1,1",
    "charge": "0",
    "multiplicity": "AUTO",
    "uks": False,
    "geo_optimizer": "BFGS",
    "charge_print": "None",
    "molden_print": False,
    "output_molden": False,
    "cube_print": "None",
    "cutoff": "400",
    "rel_cutoff": "55",
    "diag_max_scf": "1000",
    "diag_eps_scf": "5.0E-06",
    "ot_inner_max_scf": "25",
    "ot_inner_eps_scf": "5.0E-06",
    "ot_outer_max_scf": "20",
    "ot_outer_eps_scf": "5.0E-06",
    "mixing_alpha": "0.2",
    "nbroyden": "16",
    "soft_element_strategy": False,
    "plus_u_method": "MULLIKEN",
    "enable_dft_u": False,
    "enable_magnetism": False,
    "dft_u_rows": "",
    "magnetization_rows": "",
    "fixed_atoms": "",
    "fixed_atoms_mode": "MANUAL",
    "freeze_bottom_z_range_percent": "70",
    "fixed_atoms_exclude_indices": "",
    "slurm_enabled": False,
    "slurm_template": "local",
    "slurm_preset": "general_64_4",
    "slurm_nodes": "4",
    "slurm_cores": "64",
    "slurm_cores_per_node_mode": "default",
    "slurm_cores_per_node": "16",
}


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-+() ]+", "_", name.strip())
    return cleaned or "structure.cif"


def _safe_project(name: str, fallback: str) -> str:
    name = Path(name.strip()).name if name.strip() else fallback
    if name.lower().endswith(".inp"):
        name = name[:-4]
    return re.sub(r"[^\w.\-+]+", "_", name)


def _safe_folder_name(name: str, fallback: str = "case") -> str:
    cleaned = re.sub(r"[^\w.\-+ ]+", "_", Path(str(name or "").strip()).name)
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def _write_structure_text(path: Path, content: str) -> None:
    normalized = _normalize_structure_text(content)
    with path.open("w", encoding="utf-8", errors="replace", newline="") as handle:
        handle.write(normalized)


def _normalize_structure_text(content: str) -> str:
    return content.replace("\r\r\n", "\r\n")


def _canonical_structure_text(content: str) -> str:
    return _normalize_structure_text(content).replace("\r\n", "\n").replace("\r", "\n")


def _make_diff(raw: str, patched: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            raw.splitlines(),
            patched.splitlines(),
            fromfile="multiwfn.raw.inp",
            tofile="cp2k_forge.patched.inp",
            lineterm="",
        )
    )


def _structure_content_from_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    file_info = payload.get("file") or {}
    filename = str(payload.get("filename") or file_info.get("name") or "structure.gjf")
    source_path = str(payload.get("source_path") or file_info.get("path") or payload.get("path") or "").strip().strip('"')
    content = str(payload.get("content") or file_info.get("content") or "")
    if not content and source_path:
        target = Path(source_path)
        if not target.is_file():
            raise ValueError(f"File not found: {target}")
        content = target.read_text(encoding="utf-8", errors="replace")
        filename = target.name
        source_path = str(target)
    if not content.strip():
        raise ValueError("No structure content was received.")
    return filename, content, source_path


def _atom_table_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    atom_table = payload.get("atom_table")
    if isinstance(atom_table, dict) and isinstance(atom_table.get("atoms"), list):
        return atom_table
    if isinstance(atom_table, list):
        return {"atoms": atom_table}
    filename, content, source_path = _structure_content_from_payload(payload)
    return parse_gjf_atom_table(content, source_name=filename, source_path=source_path)


def _same_structure_content(path: Path, content: str) -> bool:
    try:
        path_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _canonical_structure_text(path_text) == _canonical_structure_text(content)


def _decode_powershell_json_paths(text: str) -> list[Path]:
    text = text.strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(decoded, str):
        decoded_paths = [decoded]
    elif isinstance(decoded, list):
        decoded_paths = [str(item) for item in decoded if item]
    else:
        decoded_paths = []
    return [Path(item) for item in decoded_paths]


def _run_powershell_path_query(command: str) -> list[Path]:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return _decode_powershell_json_paths(completed.stdout or "")


def _explorer_selected_paths() -> list[Path]:
    command = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$shell = New-Object -ComObject Shell.Application
$paths = @()
foreach ($window in $shell.Windows()) {
  try {
    $items = $window.Document.SelectedItems()
    foreach ($item in $items) {
      if ($item.Path) { $paths += $item.Path }
    }
  } catch {}
}
$paths | ConvertTo-Json -Compress
"""
    return _run_powershell_path_query(command)


def _explorer_folder_paths() -> list[Path]:
    command = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$shell = New-Object -ComObject Shell.Application
$paths = @()
foreach ($window in $shell.Windows()) {
  try {
    $folderPath = $window.Document.Folder.Self.Path
    if ($folderPath) { $paths += $folderPath }
  } catch {}
}
$paths | ConvertTo-Json -Compress
"""
    return _run_powershell_path_query(command)


def _unique_content_matches(candidates: list[Path], content: str) -> list[Path]:
    matches: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        if _same_structure_content(candidate, content):
            matches.append(candidate)
    return matches


def _resolve_explorer_source(filenames: list[str], content: str) -> tuple[Path | None, str]:
    name_options = []
    seen_names: set[str] = set()
    for filename in filenames:
        clean = str(filename or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen_names:
            continue
        seen_names.add(key)
        name_options.append(clean)

    selected_candidates = [
        candidate
        for candidate in _explorer_selected_paths()
        if candidate.name.casefold() in seen_names
    ]
    selected_matches = _unique_content_matches(selected_candidates, content)
    if len(selected_matches) == 1:
        return selected_matches[0], "the current Explorer selection"
    if len(selected_matches) > 1:
        return None, "multiple exact Explorer selection matches"

    folder_candidates: list[Path] = []
    seen_folder_candidates: set[str] = set()
    for folder in _explorer_folder_paths():
        if not folder.is_dir():
            continue
        for filename in name_options:
            candidate = folder / filename
            key = str(candidate).lower()
            if key in seen_folder_candidates:
                continue
            seen_folder_candidates.add(key)
            folder_candidates.append(candidate)
    folder_matches = _unique_content_matches(folder_candidates, content)
    if len(folder_matches) == 1:
        return folder_matches[0], "an open Explorer folder"
    if len(folder_matches) > 1:
        return None, "multiple exact open Explorer folder matches"
    return None, ""


def _is_gjf_like(path_or_name: str | Path) -> bool:
    return Path(path_or_name).suffix.lower() in GJF_SUFFIXES


def _new_job_dir(project: str) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    job_dir = JOBS_DIR / f"{timestamp}-{project}"
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def _unique_child_dir(parent: Path, name: str) -> Path:
    base_name = _safe_folder_name(name, "case")
    candidate = parent / base_name
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    for index in range(1, 1000):
        suffix = f"_{timestamp}" if index == 1 else f"_{timestamp}_{index}"
        candidate = parent / f"{base_name}{suffix}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise ValueError(f"Could not create a unique folder for {base_name} in {parent}")


def _resolve_source_in_directory(directory: Path | None, filenames: list[str], content: str) -> Path | None:
    if not directory or not directory.is_dir():
        return None
    candidates: list[Path] = []
    seen: set[str] = set()
    for filename in filenames:
        clean = str(filename or "").strip()
        if not clean:
            continue
        candidate = directory / Path(clean).name
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    matches = _unique_content_matches(candidates, content)
    return matches[0] if len(matches) == 1 else None


def _stage_structure_input(
    filename: str,
    content: str,
    source_path_text: str,
    job_dir: Path,
    messages: list[RuleMessage],
    match_filename: str | None = None,
) -> tuple[Path, Path, Path | None]:
    source_path = Path(source_path_text) if source_path_text else None
    if source_path_text and not (source_path and source_path.is_file()):
        messages.append(
            RuleMessage(
                "warning",
                f"Local source path was not found, so the uploaded copy will be used: {source_path_text}",
            )
        )

    if source_path and source_path.is_file():
        input_path = source_path
        output_dir = source_path.parent
        archive_input_path = job_dir / filename
        if archive_input_path.resolve() != source_path.resolve():
            _write_structure_text(archive_input_path, content)
        return input_path, output_dir, source_path

    explorer_source, explorer_source_label = _resolve_explorer_source([match_filename or "", filename], content)
    if explorer_source:
        messages.append(
            RuleMessage(
                "info",
                f"Dropped file was resolved from {explorer_source_label}: {explorer_source}",
            )
        )
        input_path = explorer_source
        output_dir = explorer_source.parent
        archive_input_path = job_dir / filename
        if archive_input_path.resolve() != explorer_source.resolve():
            _write_structure_text(archive_input_path, content)
        return input_path, output_dir, explorer_source

    input_path = job_dir / filename
    _write_structure_text(input_path, content)
    messages.append(
        RuleMessage(
            "warning",
            f"Drag/drop did not provide an exact local source path. INP/GJF will be written to this job folder: {job_dir}",
        )
    )
    return input_path, job_dir, None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _write_local_slurm_script(values: dict[str, Any], project: str, output_path: Path) -> tuple[Path, str]:
    slurm_name = safe_slurm_script_name(values.get("slurm_script_name") or DEFAULT_SLURM_SCRIPT_NAME)
    slurm_path = output_path.parent / slurm_name
    slurm_project = output_path.stem or project
    slurm_text = render_local_cp2k_slurm(
        values,
        project=slurm_project,
        input_name=output_path.name,
        output_name=f"{slurm_project}.out",
    )
    with slurm_path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(slurm_text)
    return slurm_path, slurm_text


def _prepare_gjf_source(
    input_path: Path,
    content: str,
    output_dir: Path,
    job_dir: Path,
    values: dict[str, Any],
    messages: list[RuleMessage],
) -> tuple[Path | None, dict[str, Any] | None, Any | None]:
    if _is_gjf_like(input_path):
        gjf_path = input_path
        gjf_content = input_path.read_text(encoding="utf-8", errors="replace") if input_path.is_file() else content
        atom_table = parse_gjf_atom_table(gjf_content, source_name=input_path.name, source_path=str(input_path))
        messages.append(RuleMessage("info", f"Atom numbering source: {gjf_path}"))
        return gjf_path, atom_table, None

    gjf_path = output_dir / f"{input_path.stem}.gjf"
    if output_dir == job_dir:
        gjf_path = job_dir / f"{input_path.stem}.gjf"
    result = run_multiwfn_100_2_gjf(
        resolve_multiwfn_exe(values.get("multiwfn_exe", DEFAULT_MULTIWFN_EXE)),
        input_path,
        gjf_path,
    )
    if not result.ok:
        messages.append(RuleMessage("error", result.error or "Multiwfn 100-2 GJF export failed."))
        return None, None, result

    gjf_content = gjf_path.read_text(encoding="utf-8", errors="replace")
    atom_table = parse_gjf_atom_table(gjf_content, source_name=gjf_path.name, source_path=str(gjf_path))
    messages.append(RuleMessage("info", f"Multiwfn 100-2 GJF generated for atom numbering: {gjf_path}"))
    return gjf_path, atom_table, result


def _select_auto_bottom_fixed_atoms(
    atom_table: dict[str, Any],
    values: dict[str, Any],
    messages: list[RuleMessage],
) -> dict[str, Any]:
    selection = select_freeze_bottom_z_range(
        atom_table,
        percent=values.get("freeze_bottom_z_range_percent", 70),
        exclude_indices=values.get("fixed_atoms_exclude_indices", ""),
    )
    if selection.get("errors"):
        messages.extend(RuleMessage("error", text) for text in selection.get("errors", []))
        return selection

    values["fixed_atoms"] = selection.get("fixed_atom_string", "")
    preview = selection.get("preview", {})
    for warning in selection.get("warnings", []):
        messages.append(RuleMessage("warning", warning))
    messages.append(
        RuleMessage(
            "info",
            f"Auto bottom fixed atoms selected {preview.get('fixed_atom_count', 0)} atoms: {values['fixed_atoms']}",
        )
    )
    return selection


def prepare_auto_fixed_preview(payload: dict[str, Any]) -> dict[str, Any]:
    file_info = payload.get("file") or {}
    original_filename = str(file_info.get("name", "structure.cif"))
    filename = _sanitize_filename(original_filename)
    content = str(file_info.get("content", ""))
    if not content.strip():
        raise ValueError("No structure file content was received.")

    raw_values = dict(DEFAULT_VALUES)
    raw_values.update(payload.get("values") or {})
    if payload.get("percent") is not None:
        raw_values["freeze_bottom_z_range_percent"] = payload.get("percent")
    if payload.get("exclude_indices") is not None:
        raw_values["fixed_atoms_exclude_indices"] = payload.get("exclude_indices")

    element_counts = detect_element_counts(filename, content)
    elements = list(element_counts)
    normalized = normalize_spec(raw_values, elements, element_counts)
    values = normalized.values
    messages = list(normalized.messages)
    project = _safe_project(str(values.get("project", "")), Path(filename).stem)
    job_dir = _new_job_dir(f"preview-{project}")
    source_path_text = str(file_info.get("path") or values.get("source_path") or "").strip().strip('"')
    input_path, output_dir, source_path = _stage_structure_input(
        filename,
        content,
        source_path_text,
        job_dir,
        messages,
        match_filename=original_filename,
    )
    gjf_path, atom_table, gjf_result = _prepare_gjf_source(input_path, content, output_dir, job_dir, values, messages)
    if not (gjf_path and atom_table):
        return {
            "ok": False,
            "error": "Could not prepare a Multiwfn 100-2 GJF atom table.",
            "messages": [m.__dict__ for m in messages],
            "job_dir": str(job_dir),
            "source_path": str(source_path) if source_path else "",
            "gjf_path": str(gjf_path) if gjf_path else "",
            "multiwfn_log": gjf_result.log[-12000:] if gjf_result else "",
            "command_script": gjf_result.command_script if gjf_result else "",
        }

    reference_info = payload.get("slab_reference_file") or payload.get("reference_file") or {}
    reference_atom_table: dict[str, Any] | None = None
    reference_gjf_path: Path | None = None
    reference_gjf_result = None
    if isinstance(reference_info, dict) and str(reference_info.get("content", "")).strip():
        reference_original_filename = str(reference_info.get("name", "clean_slab.cif"))
        reference_filename = _sanitize_filename(reference_original_filename)
        reference_content = str(reference_info.get("content", ""))
        reference_source_path_text = str(reference_info.get("path") or "").strip().strip('"')
        reference_job_dir = job_dir / "reference_slab"
        reference_job_dir.mkdir(parents=True, exist_ok=True)
        ref_messages: list[RuleMessage] = []
        reference_input_path, reference_output_dir, _reference_source_path = _stage_structure_input(
            reference_filename,
            reference_content,
            reference_source_path_text,
            reference_job_dir,
            ref_messages,
            match_filename=reference_original_filename,
        )
        messages.extend(ref_messages)
        reference_gjf_path, reference_atom_table, reference_gjf_result = _prepare_gjf_source(
            reference_input_path,
            reference_content,
            reference_output_dir,
            reference_job_dir,
            values,
            messages,
        )
        if not (reference_gjf_path and reference_atom_table):
            return {
                "ok": False,
                "error": "Could not prepare the clean slab reference GJF atom table.",
                "messages": [m.__dict__ for m in messages],
                "job_dir": str(job_dir),
                "source_path": str(source_path) if source_path else "",
                "gjf_path": str(gjf_path),
                "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
                "atom_table": atom_table,
                "multiwfn_log": ((gjf_result.log + "\n\n") if gjf_result else "")
                + (reference_gjf_result.log[-12000:] if reference_gjf_result else ""),
                "command_script": ((gjf_result.command_script + "\n") if gjf_result else "")
                + (reference_gjf_result.command_script if reference_gjf_result else ""),
            }
        selection = select_freeze_bottom_z_range_from_reference(
            atom_table,
            reference_atom_table,
            percent=values.get("freeze_bottom_z_range_percent", 70),
            exclude_indices=values.get("fixed_atoms_exclude_indices", ""),
        )
        if selection.get("errors"):
            messages.extend(RuleMessage("error", text) for text in selection.get("errors", []))
        else:
            values["fixed_atoms"] = selection.get("fixed_atom_string", "")
            preview = selection.get("preview", {})
            messages.append(
                RuleMessage(
                    "info",
                    f"Auto bottom fixed atoms selected from clean slab reference: {preview.get('fixed_atom_count', 0)} atoms: {values['fixed_atoms']}",
                )
            )
        for warning in selection.get("warnings", []):
            messages.append(RuleMessage("warning", warning))
    else:
        selection = _select_auto_bottom_fixed_atoms(atom_table, values, messages)
    ok = not selection.get("errors")
    return {
        "ok": ok,
        "error": "" if ok else "Auto bottom fixed atom detection failed.",
        "messages": [m.__dict__ for m in messages],
        "job_dir": str(job_dir),
        "source_path": str(source_path) if source_path else "",
        "gjf_path": str(gjf_path),
        "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
        "reference_atom_table": reference_atom_table,
        "atom_table": atom_table,
        "result": selection,
        "multiwfn_log": (((gjf_result.log + "\n\n") if gjf_result else "") + (reference_gjf_result.log if reference_gjf_result else ""))[-12000:],
        "command_script": ((gjf_result.command_script + "\n") if gjf_result else "")
        + (reference_gjf_result.command_script if reference_gjf_result else ""),
    }


def generate_job(payload: dict[str, Any]) -> dict[str, Any]:
    file_info = payload.get("file") or {}
    original_filename = str(file_info.get("name", "structure.cif"))
    filename = _sanitize_filename(original_filename)
    content = str(file_info.get("content", ""))
    if not content.strip():
        raise ValueError("No structure file content was received.")

    raw_values = dict(DEFAULT_VALUES)
    raw_values.update(payload.get("values") or {})

    element_counts = detect_element_counts(filename, content)
    elements = list(element_counts)
    normalized = normalize_spec(raw_values, elements, element_counts)
    values = normalized.values
    messages = list(normalized.messages)
    source_path_text = str(file_info.get("path") or values.get("source_path") or "").strip().strip('"')
    if values.get("scf_method") == "OT" and str(values.get("ot_minimizer", "DIIS")).upper() != "DIIS":
        messages.append(
            RuleMessage(
                "warning",
                "OT MINIMIZER selection was not patched directly. Current Multiwfn 3.8 CP2K generator probing did not expose a DIIS/CG menu, so Multiwfn's generated value is kept.",
            )
        )
    task = str(values.get("task", "ENERGY"))
    fixed_atoms_mode = str(values.get("fixed_atoms_mode", "MANUAL")).upper()

    project = _safe_project(str(values.get("project", "")), Path(filename).stem)
    job_dir = _new_job_dir(project)
    input_path, output_dir, source_path = _stage_structure_input(
        filename,
        content,
        source_path_text,
        job_dir,
        messages,
        match_filename=original_filename,
    )
    prepared_gjf_path: Path | None = None
    gjf_result = None
    reference_gjf_path: Path | None = None
    reference_gjf_result = None
    atom_table: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None

    if task in {"GEO_OPT", "CELL_OPT"} and fixed_atoms_mode == "AUTO_BOTTOM":
        prepared_gjf_path, atom_table, gjf_result = _prepare_gjf_source(
            input_path,
            content,
            output_dir,
            job_dir,
            values,
            messages,
        )
        if not (prepared_gjf_path and atom_table):
            return {
                "ok": False,
                "error": "Could not prepare a Multiwfn 100-2 GJF source for auto bottom fixed atoms.",
                "messages": [m.__dict__ for m in messages],
                "multiwfn_log": gjf_result.log[-12000:] if gjf_result else "",
                "command_script": gjf_result.command_script if gjf_result else "",
                "job_dir": str(job_dir),
            }
        reference_info = payload.get("slab_reference_file") or payload.get("reference_file") or {}
        if isinstance(reference_info, dict) and str(reference_info.get("content", "")).strip():
            reference_original_filename = str(reference_info.get("name", "clean_slab.cif"))
            reference_filename = _sanitize_filename(reference_original_filename)
            reference_content = str(reference_info.get("content", ""))
            reference_source_path_text = str(reference_info.get("path") or "").strip().strip('"')
            reference_job_dir = job_dir / "reference_slab"
            reference_job_dir.mkdir(parents=True, exist_ok=True)
            ref_messages: list[RuleMessage] = []
            reference_input_path, reference_output_dir, _reference_source_path = _stage_structure_input(
                reference_filename,
                reference_content,
                reference_source_path_text,
                reference_job_dir,
                ref_messages,
                match_filename=reference_original_filename,
            )
            messages.extend(ref_messages)
            reference_gjf_path, reference_atom_table, reference_gjf_result = _prepare_gjf_source(
                reference_input_path,
                reference_content,
                reference_output_dir,
                reference_job_dir,
                values,
                messages,
            )
            if not (reference_gjf_path and reference_atom_table):
                return {
                    "ok": False,
                    "error": "Could not prepare the clean slab reference GJF source for auto bottom fixed atoms.",
                    "messages": [m.__dict__ for m in messages],
                    "multiwfn_log": (((gjf_result.log + "\n\n") if gjf_result else "") + (reference_gjf_result.log if reference_gjf_result else ""))[-12000:],
                    "command_script": ((gjf_result.command_script + "\n") if gjf_result else "")
                    + (reference_gjf_result.command_script if reference_gjf_result else ""),
                    "job_dir": str(job_dir),
                    "gjf_path": str(prepared_gjf_path),
                    "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
                }
            selection = select_freeze_bottom_z_range_from_reference(
                atom_table,
                reference_atom_table,
                percent=values.get("freeze_bottom_z_range_percent", 70),
                exclude_indices=values.get("fixed_atoms_exclude_indices", ""),
            )
            if selection.get("errors"):
                messages.extend(RuleMessage("error", text) for text in selection.get("errors", []))
            else:
                values["fixed_atoms"] = selection.get("fixed_atom_string", "")
                preview = selection.get("preview", {})
                messages.append(
                    RuleMessage(
                        "info",
                        f"Auto bottom fixed atoms selected from clean slab reference: {preview.get('fixed_atom_count', 0)} atoms: {values['fixed_atoms']}",
                    )
                )
            for warning in selection.get("warnings", []):
                messages.append(RuleMessage("warning", warning))
        else:
            selection = _select_auto_bottom_fixed_atoms(atom_table, values, messages)
        if selection.get("errors"):
            return {
                "ok": False,
                "error": "Auto bottom fixed atom detection failed.",
                "messages": [m.__dict__ for m in messages],
                "multiwfn_log": (((gjf_result.log + "\n\n") if gjf_result else "") + (reference_gjf_result.log if reference_gjf_result else ""))[-12000:],
                "command_script": ((gjf_result.command_script + "\n") if gjf_result else "")
                + (reference_gjf_result.command_script if reference_gjf_result else ""),
                "job_dir": str(job_dir),
                "gjf_path": str(prepared_gjf_path),
                "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
            }
        input_path = prepared_gjf_path
        messages.append(RuleMessage("info", "CP2K input generation will use the same GJF atom order as the auto fixed atom list."))
    elif task in {"GEO_OPT", "CELL_OPT"} and str(values.get("fixed_atoms", "")).strip():
        messages.append(RuleMessage("info", "Fixed atoms will be set through Multiwfn option 9."))

    output_path = output_dir / f"{project}.inp"
    messages.append(RuleMessage("info", f"Final INP path: {output_path}"))
    raw_output_path = job_dir / f"{project}.multiwfn.raw.inp"
    command_path = job_dir / f"{project}.multiwfn_commands.txt"
    gjf_command_path = job_dir / f"{project}.multiwfn_100_2_commands.txt"
    gjf_log_path = job_dir / f"{project}.multiwfn_100_2.log"
    reference_gjf_command_path = job_dir / f"{project}.reference_slab_multiwfn_100_2_commands.txt"
    reference_gjf_log_path = job_dir / f"{project}.reference_slab_multiwfn_100_2.log"
    spec_path = job_dir / f"{project}.spec.json"

    if gjf_result:
        gjf_command_path.write_text(gjf_result.command_script, encoding="utf-8")
        gjf_log_path.write_text(gjf_result.log, encoding="utf-8")
    if reference_gjf_result:
        reference_gjf_command_path.write_text(reference_gjf_result.command_script, encoding="utf-8")
        reference_gjf_log_path.write_text(reference_gjf_result.log, encoding="utf-8")

    mw_result = run_multiwfn(
        resolve_multiwfn_exe(values.get("multiwfn_exe", DEFAULT_MULTIWFN_EXE)),
        input_path,
        output_path,
        values,
    )
    combined_command_script = ""
    if gjf_result:
        combined_command_script += "# Multiwfn 100-2 GJF export\n" + gjf_result.command_script + "\n"
    if reference_gjf_result:
        combined_command_script += "# Multiwfn 100-2 clean slab reference GJF export\n" + reference_gjf_result.command_script + "\n"
    combined_command_script += "# Multiwfn CP2K input generation\n" + mw_result.command_script
    command_path.write_text(combined_command_script, encoding="utf-8")
    combined_log = (
        ((gjf_result.log + "\n\n") if gjf_result else "")
        + ((reference_gjf_result.log + "\n\n") if reference_gjf_result else "")
        + mw_result.log
    )

    if not mw_result.ok:
        return {
            "ok": False,
            "error": mw_result.error,
            "messages": [m.__dict__ for m in messages],
            "multiwfn_log": combined_log[-12000:],
            "command_script": combined_command_script,
            "job_dir": str(job_dir),
            "gjf_path": str(prepared_gjf_path) if prepared_gjf_path else "",
        }

    raw_text = output_path.read_text(encoding="utf-8", errors="replace")
    raw_output_path.write_text(raw_text, encoding="utf-8")
    patch_result = apply_cp2k_forge_patches(raw_text, values, elements)
    output_path.write_text(patch_result.text, encoding="utf-8")
    slurm_path: Path | None = None
    slurm_text = ""
    if _truthy(values.get("slurm_enabled")):
        try:
            slurm_path, slurm_text = _write_local_slurm_script(values, project, output_path)
            messages.append(RuleMessage("info", f"Slurm script written: {slurm_path}"))
        except ValueError as exc:
            messages.append(RuleMessage("error", f"Slurm script generation failed: {exc}"))
            return {
                "ok": False,
                "error": f"Slurm script generation failed: {exc}",
                "output_path": str(output_path),
                "raw_output_path": str(raw_output_path),
                "command_path": str(command_path),
                "job_dir": str(job_dir),
                "source_path": str(source_path) if source_path else "",
                "messages": [m.__dict__ for m in messages],
                "patch_notes": patch_result.notes,
                "raw_input": raw_text,
                "patched_input": patch_result.text,
                "diff": _make_diff(raw_text, patch_result.text),
                "multiwfn_log": combined_log[-20000:],
                "command_script": combined_command_script,
            }

    spec_path.write_text(
        json.dumps(
            {
                "version": __version__,
                "source_file": str(input_path),
                "output_file": str(output_path),
                "elements": elements,
                "element_counts": element_counts,
                "values": values,
                "source_path": str(source_path) if source_path else "",
                "prepared_gjf_path": str(prepared_gjf_path) if prepared_gjf_path else "",
                "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
                "slurm_path": str(slurm_path) if slurm_path else "",
                "messages": [m.__dict__ for m in messages],
                "patch_notes": patch_result.notes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "output_path": str(output_path),
        "raw_output_path": str(raw_output_path),
        "command_path": str(command_path),
        "spec_path": str(spec_path),
        "job_dir": str(job_dir),
        "slurm_path": str(slurm_path) if slurm_path else "",
        "slurm_text": slurm_text,
        "source_path": str(source_path) if source_path else "",
        "gjf_path": str(prepared_gjf_path) if prepared_gjf_path else "",
        "reference_gjf_path": str(reference_gjf_path) if reference_gjf_path else "",
        "auto_fixed_selection": selection or {},
        "elements": elements,
        "element_counts": element_counts,
        "messages": [m.__dict__ for m in messages],
        "patch_notes": patch_result.notes,
        "raw_input": raw_text,
        "patched_input": patch_result.text,
        "diff": _make_diff(raw_text, patch_result.text),
        "multiwfn_log": combined_log[-20000:],
        "command_script": combined_command_script,
    }


def _template_source_dir(payload: dict[str, Any], messages: list[RuleMessage]) -> Path | None:
    template_info = payload.get("template_file") or payload.get("file") or {}
    template_filename = str(template_info.get("name") or "template.structure")
    template_content = str(template_info.get("content") or "")
    source_path_text = str(
        payload.get("batch_source_dir")
        or template_info.get("path")
        or (payload.get("values") or {}).get("source_path")
        or ""
    ).strip().strip('"')
    if source_path_text:
        source_path = Path(source_path_text)
        if source_path.is_file():
            return source_path.parent
        if source_path.is_dir():
            return source_path

    if template_content.strip():
        resolved, resolved_label = _resolve_explorer_source(
            [template_filename, _sanitize_filename(template_filename)],
            template_content,
        )
        if resolved:
            messages.append(RuleMessage("info", f"Template file was resolved from {resolved_label}: {resolved}"))
            return resolved.parent
    return None


def _batch_path_key(path_text: str) -> str:
    clean = str(path_text or "").strip().strip('"')
    if not clean:
        return ""
    try:
        return str(Path(clean).resolve()).casefold()
    except OSError:
        return clean.casefold()


def _collect_batch_inputs(template_info: dict[str, Any], batch_files: list[Any]) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_contents: set[tuple[str, str]] = set()

    def append_file(raw_info: Any, role: str) -> None:
        if not isinstance(raw_info, dict):
            return
        name = str(raw_info.get("name") or "").strip()
        path_key = _batch_path_key(str(raw_info.get("path") or ""))
        content = str(raw_info.get("content") or "")
        content_key = (name.casefold(), _canonical_structure_text(content)) if name and content.strip() else None
        if path_key and path_key in seen_paths:
            return
        if content_key and content_key in seen_contents:
            return
        item = dict(raw_info)
        item["_batch_role"] = role
        combined.append(item)
        if path_key:
            seen_paths.add(path_key)
        if content_key:
            seen_contents.add(content_key)

    append_file(template_info, "template")
    for raw_file in batch_files:
        append_file(raw_file, "batch")
    return combined


def batch_generate_jobs(payload: dict[str, Any]) -> dict[str, Any]:
    template_info = payload.get("template_file") or payload.get("file") or {}
    batch_files = payload.get("files") or payload.get("batch_files") or []
    if not isinstance(batch_files, list) or not batch_files:
        batch_files = []
    batch_inputs = _collect_batch_inputs(template_info if isinstance(template_info, dict) else {}, batch_files)
    if not batch_inputs:
        raise ValueError("No template or batch structure files were received.")

    messages: list[RuleMessage] = []
    source_dir = _template_source_dir(payload, messages)
    if not source_dir:
        return {
            "ok": False,
            "error": "Batch generation needs an exact template source folder. Load the first structure through Local structure path, or drag from an open Explorer folder so the source path can be resolved.",
            "messages": [m.__dict__ for m in messages],
            "results": [],
        }

    output_mode = str(payload.get("batch_output_mode") or payload.get("output_mode") or "separate_folders")
    output_mode = output_mode.strip().lower().replace("-", "_")
    if output_mode not in {"separate_folders", "source_folder"}:
        output_mode = "separate_folders"

    raw_values = dict(DEFAULT_VALUES)
    raw_values.update(payload.get("values") or {})
    raw_values["source_path"] = ""

    results: list[dict[str, Any]] = []
    success_count = 0
    failure_count = 0

    for index, item in enumerate(batch_inputs, start=1):
        file_info = item if isinstance(item, dict) else {}
        role = str(file_info.get("_batch_role") or "batch")
        original_filename = str(file_info.get("name") or f"structure_{index}")

        filename = _sanitize_filename(original_filename)
        content = str(file_info.get("content") or "")
        source_path_text = str(file_info.get("path") or "").strip().strip('"')
        source_path = Path(source_path_text) if source_path_text else None
        if source_path and (not source_path.is_file() or source_path.parent.resolve() != source_dir.resolve()):
            source_path = None

        if source_path and source_path.is_file():
            if not content.strip():
                content = source_path.read_text(encoding="utf-8", errors="replace")
            elif not _same_structure_content(source_path, content):
                source_path = None

        if not source_path:
            source_path = _resolve_source_in_directory(source_dir, [original_filename, filename], content)

        if not content.strip() and source_path and source_path.is_file():
            content = source_path.read_text(encoding="utf-8", errors="replace")

        if not content.strip():
            failure_count += 1
            results.append({"ok": False, "name": original_filename, "error": "No structure file content was received."})
            continue

        if not source_path:
            failure_count += 1
            results.append(
                {
                    "ok": False,
                    "name": original_filename,
                    "error": f"Could not confirm {original_filename} inside the template source folder: {source_dir}",
                }
            )
            continue

        case_stem = _safe_project(Path(filename).stem, f"case_{index}")
        if output_mode == "source_folder":
            case_dir = source_dir
            input_path_for_job = source_path
        else:
            case_dir = _unique_child_dir(source_dir, case_stem)
            input_path_for_job = case_dir / filename
            if source_path.is_file():
                shutil.copy2(source_path, input_path_for_job)
            else:
                _write_structure_text(input_path_for_job, content)

        values = dict(raw_values)
        values["project"] = case_stem
        values["source_path"] = str(input_path_for_job)
        if _truthy(values.get("slurm_enabled")):
            if output_mode == "source_folder":
                values["slurm_script_name"] = f"{case_stem}.slurm"
            else:
                values.pop("slurm_script_name", None)
        result = generate_job(
            {
                "file": {"name": filename, "path": str(input_path_for_job), "content": content},
                "slab_reference_file": payload.get("slab_reference_file"),
                "values": values,
            }
        )
        compact = {
            "ok": bool(result.get("ok")),
            "name": original_filename,
            "role": role,
            "output_mode": output_mode,
            "case_dir": str(case_dir),
            "input_copy_path": str(input_path_for_job),
            "output_path": result.get("output_path", ""),
            "slurm_path": result.get("slurm_path", ""),
            "job_dir": result.get("job_dir", ""),
            "source_path": str(source_path),
            "messages": result.get("messages", []),
            "patch_notes": result.get("patch_notes", []),
            "error": result.get("error", ""),
        }
        if result.get("ok"):
            success_count += 1
        else:
            failure_count += 1
        results.append(compact)

    summary = f"Batch generation finished: {success_count} succeeded, {failure_count} failed."
    messages.append(RuleMessage("info", summary))
    return {
        "ok": failure_count == 0,
        "summary": summary,
        "source_dir": str(source_dir),
        "output_mode": output_mode,
        "success_count": success_count,
        "failure_count": failure_count,
        "messages": [m.__dict__ for m in messages],
        "results": results,
    }
