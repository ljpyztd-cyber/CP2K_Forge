from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


DEFAULT_SLURM_PRESET = "general_64_4"
DEFAULT_SLURM_SCRIPT_NAME = "cp2k.slurm"
DEFAULT_SLURM_PARTITION = "q_ysuan"
DEFAULT_HPCCUBE_PARTITION = "xahcnormal"
HPCCUBE_CP2K_ENV = "/work/home/jsyadmin/apprepo/cp2k/v2026.1-glic235/scripts/env.sh"
HPCCUBE_CP2K_SETUP = "/opt/cp2k-2026.1/tools/toolchain/install/setup"

SLURM_PRESETS: dict[str, dict[str, Any]] = {
    "general_64_4": {
        "nodes": 4,
        "cores": 64,
        "cores_per_node": 16,
        "memory_saving": False,
        "extra_exports": False,
    },
    "small_32_1": {
        "nodes": 1,
        "cores": 32,
        "cores_per_node": 32,
        "memory_saving": False,
        "extra_exports": False,
    },
    "memory_saving": {
        "nodes": 16,
        "cores": 128,
        "cores_per_node": 8,
        "memory_saving": True,
        "extra_exports": True,
    },
    "ssh_32_1": {
        "nodes": 1,
        "cores": 32,
        "cores_per_node": 32,
        "memory_saving": False,
        "extra_exports": False,
        "style": "ssh",
    },
}


def render_local_cp2k_slurm(values: dict[str, Any], project: str, input_name: str, output_name: str) -> str:
    preset_name = str(values.get("slurm_preset") or DEFAULT_SLURM_PRESET).strip()
    preset = SLURM_PRESETS.get(preset_name, SLURM_PRESETS[DEFAULT_SLURM_PRESET])
    style = str(values.get("slurm_style") or values.get("slurm_template") or preset.get("style") or "local").strip().lower()
    nodes = _positive_int(values.get("slurm_nodes"), int(preset["nodes"]), "Slurm node count")
    cores = _positive_int(values.get("slurm_cores"), int(preset["cores"]), "Slurm core count")
    per_node_mode = str(values.get("slurm_cores_per_node_mode") or "default").strip().lower()
    default_per_node = _default_cores_per_node(nodes, cores, int(preset["cores_per_node"]))
    cores_per_node = default_per_node
    if per_node_mode == "custom":
        cores_per_node = _positive_int(values.get("slurm_cores_per_node"), default_per_node, "Slurm cores per node")

    if style in {"ssh", "ssh_hpccube", "hpccube", "hpccube_apprepo", "apprepo"}:
        return render_hpccube_cp2k_slurm(values, project, input_name, output_name, nodes, cores_per_node)

    job_name = _safe_slurm_token(project, "Slurm job name")
    input_file = _safe_filename(input_name, "CP2K input filename")
    output_file = _safe_filename(output_name, "CP2K output filename")
    memory_saving = bool(preset.get("memory_saving"))
    use_map_by = memory_saving or per_node_mode == "custom"

    lines = [
        "#!/bin/sh",
        f"#SBATCH -J {job_name}",
        f"#SBATCH -p {DEFAULT_SLURM_PARTITION}",
        "#SBATCH -o job_%j.out",
        "#SBATCH -e job_%j.err",
        f"#SBATCH -N {nodes}",
        f"#SBATCH -n {cores}",
    ]
    if memory_saving:
        lines.append("#SBATCH --mem-per-cpu=4G")

    lines.extend(
        [
            "",
            "source ~/yeesuan/envs/cp2k_env.sh",
            "",
            "echo Running on hosts",
            "echo Time is $(date)",
            "echo Directory is $PWD",
            "echo this job runs on the following nodes:",
            "echo $SLURM_JOB_NODELIST",
            "export OMP_NUM_THREADS=1",
        ]
    )
    if bool(preset.get("extra_exports")):
        lines.extend(
            [
                "export I_MPI_PIN=1",
                "export I_MPI_PIN_DOMAIN=core",
                "export I_MPI_DAPL_BUFFER_SIZE=1024",
            ]
        )

    map_options = f" --map-by ppr:{cores_per_node}:node --bind-to core" if use_map_by else ""
    cp2k_input = f"-i {input_file}" if memory_saving else input_file
    lines.extend(
        [
            "",
            f"mpirun -np {cores}{map_options} cp2k.psmp {cp2k_input} > {output_file}",
            "",
        ]
    )
    return "\n".join(lines)


def render_hpccube_cp2k_slurm(
    values: dict[str, Any],
    project: str,
    input_name: str,
    output_name: str,
    nodes: int | None = None,
    cores_per_node: int | None = None,
) -> str:
    preset_name = str(values.get("slurm_preset") or DEFAULT_SLURM_PRESET).strip()
    preset = SLURM_PRESETS.get(preset_name, SLURM_PRESETS[DEFAULT_SLURM_PRESET])
    nodes = nodes if nodes is not None else _positive_int(values.get("slurm_nodes"), int(preset["nodes"]), "Slurm node count")
    cores = _positive_int(values.get("slurm_cores"), int(preset["cores"]), "Slurm core count")
    if cores_per_node is None:
        per_node_mode = str(values.get("slurm_cores_per_node_mode") or "default").strip().lower()
        default_per_node = _default_cores_per_node(nodes, cores, int(preset["cores_per_node"]))
        cores_per_node = default_per_node
        if per_node_mode == "custom":
            cores_per_node = _positive_int(values.get("slurm_cores_per_node"), default_per_node, "Slurm cores per node")

    input_file = _safe_filename(input_name, "CP2K input filename")
    output_file = _safe_filename(output_name, "CP2K output filename")
    job_name = _safe_slurm_token(Path(input_file).stem or project, "Slurm job name")
    partition = _safe_slurm_token(values.get("slurm_partition") or DEFAULT_HPCCUBE_PARTITION, "Slurm partition")

    lines = [
        "#!/bin/bash",
        f"#SBATCH -J {job_name}",
        f"#SBATCH -p {partition}",
        f"#SBATCH -N {nodes}",
        f"#SBATCH --ntasks-per-node={cores_per_node}",
        "#SBATCH -o slurm-%j.out",
        "#SBATCH -e slurm-%j.err",
        "",
        "set -euo pipefail",
        "module purge",
        f"source {HPCCUBE_CP2K_ENV}",
        "",
        "echo Running on hosts",
        "echo Time is $(date)",
        "echo Directory is $PWD",
        "echo this job runs on the following nodes:",
        "echo $SLURM_JOB_NODELIST",
        "export OMP_NUM_THREADS=1",
        f'export COMMAND="cp2k.psmp -i {input_file} > {output_file}"',
        "",
        'srun --mpi=pmix_v3 singularity exec -B /public/software/apprepo ${WHERE_IS_SIF} bash -c "',
        f"source {HPCCUBE_CP2K_SETUP}",
        "$COMMAND",
        '"',
        "",
    ]
    return "\n".join(lines)


def safe_slurm_script_name(value: Any, default: str = DEFAULT_SLURM_SCRIPT_NAME) -> str:
    text = str(value or "").strip() or default
    name = _safe_filename(text, "Slurm script filename")
    return name if name.lower().endswith(".slurm") else f"{Path(name).stem}.slurm"


def _default_cores_per_node(nodes: int, cores: int, preset_default: int) -> int:
    if nodes <= 0:
        return preset_default
    if cores % nodes == 0:
        return max(1, cores // nodes)
    return max(1, math.ceil(cores / nodes))


def _positive_int(value: Any, default: int, field: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        number = default
    if number <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return number


def _safe_slurm_token(value: Any, field: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.+\-]+", "_", str(value or "").strip())
    token = token.strip("._-")
    if not token:
        raise ValueError(f"{field} is empty.")
    if any(ord(char) < 32 or ord(char) > 126 for char in token):
        raise ValueError(f"{field} must be ASCII.")
    return token


def _safe_filename(value: Any, field: str) -> str:
    name = Path(str(value or "").strip()).name
    name = re.sub(r"[^A-Za-z0-9_.+\-]+", "_", name).strip("._-")
    if not name:
        raise ValueError(f"{field} is empty.")
    if any(ord(char) < 32 or ord(char) > 126 for char in name):
        raise ValueError(f"{field} must be ASCII.")
    return name
