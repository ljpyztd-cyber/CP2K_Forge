# CP2K_Forge

**作者 / Author:** Brant Li from City University of Hong Kong ([jiapeili-c@my.cityu.edu.hk](mailto:jiapeili-c@my.cityu.edu.hk))

> **Slurm 平台说明：** 当前 Slurm 脚本生成功能暂时只适用于作者使用的超算平台；如需协助修改或适配其他平台，请通过上述邮箱联系作者。
>
> **Slurm platform notice:** The current Slurm script generator is temporarily specific to the HPC platform used by the author. For assistance modifying or adapting it to another platform, contact the author at the email address above.

## 重要：Multiwfn 致谢与引用要求 | Important: Multiwfn Acknowledgement and Citation Requirement

> **中文：** CP2K_Forge 的 CP2K 输入文件生成流程调用了 Multiwfn。谨向北京科音卢天老师（Sobereva）致谢。凡使用 CP2K_Forge 生成的输入文件或计算工作流开展研究并发表论文，包括为他人进行的代算，必须在论文**正文**中至少引用下面两篇 Multiwfn 文献；仅在补充信息中引用不符合 Multiwfn 的引用要求。
>
> **English:** CP2K_Forge uses Multiwfn in its CP2K input-generation workflow. We gratefully acknowledge Prof. Tian Lu (Sobereva) of Beijing Kein Research Center for Natural Sciences. Any publication based on CP2K_Forge-generated inputs or workflows, including calculations performed for third parties, must cite **both** Multiwfn papers below in the **main text**. Citing them only in the Supporting Information does not satisfy the Multiwfn citation requirement.

1. Tian Lu and Feiwu Chen, "Multiwfn: A Multifunctional Wavefunction Analyzer," *Journal of Computational Chemistry* **33**, 580-592 (2012). [https://doi.org/10.1002/jcc.22885](https://doi.org/10.1002/jcc.22885)
2. Tian Lu, "A comprehensive electron wavefunction analysis toolbox for chemists, Multiwfn," *Journal of Chemical Physics* **161**, 082503 (2024). [https://doi.org/10.1063/5.0216272](https://doi.org/10.1063/5.0216272)

**Multiwfn 主页 / Homepage:** [http://sobereva.com/multiwfn](http://sobereva.com/multiwfn)

Multiwfn 是独立的第三方软件，本仓库不包含 Multiwfn 本体。请同时遵守 Multiwfn 自身的许可证、使用条款和引用说明。

Multiwfn is independent third-party software and is not distributed in this repository. Users must also comply with its license, terms of use, and citation instructions.

## 安装方式 | Installation

### 中文

1. 安装 Windows 10/11、Python 3.10 或更高版本，并确认 `python` 和 `pip` 可在 PowerShell 中使用。
2. 从 [Multiwfn 主页](http://sobereva.com/multiwfn) 下载并完整解压 Multiwfn。不要只复制 `Multiwfn.exe`，其配套文件需要保留在同一目录中。
3. 克隆本仓库，或通过 GitHub 的 **Code > Download ZIP** 下载并解压源码：

```powershell
git clone https://github.com/ljpyztd-cyber/CP2K_Forge.git
cd CP2K_Forge
python -m pip install -r CP2K_FORGE_EXE\requirements.txt
```

4. 启动桌面程序：

```powershell
python CP2K_FORGE_EXE\run.py
```

5. 首次启动后，在“设置”中选择完整的 Multiwfn 安装目录或 `Multiwfn.exe`。

### English

1. Install Windows 10/11 and Python 3.10 or newer. Confirm that `python` and `pip` are available in PowerShell.
2. Download and fully extract Multiwfn from the [Multiwfn homepage](http://sobereva.com/multiwfn). Keep all supporting files with `Multiwfn.exe`; do not copy the executable alone.
3. Clone this repository, or use **Code > Download ZIP** on GitHub and extract the source:

```powershell
git clone https://github.com/ljpyztd-cyber/CP2K_Forge.git
cd CP2K_Forge
python -m pip install -r CP2K_FORGE_EXE\requirements.txt
```

4. Start the desktop application:

```powershell
python CP2K_FORGE_EXE\run.py
```

5. After the first launch, select the complete Multiwfn installation directory or `Multiwfn.exe` in Settings.

## 中文说明

### 项目简介

CP2K_Forge 是一个 Windows 桌面工具，用于通过经过验证的 Multiwfn 生成链路创建 CP2K `.inp` 文件，并提供 PyQt 分子/晶体结构可视化、固定原子选择、批量生成和本地 Slurm 脚本生成功能。

当前版本：

- 桌面程序：`v0.4.9`
- 稳定 INP 生成后端：`v0.2.18`

### 主要功能

- 生成 `ENERGY`、`GEO_OPT` 和 `CELL_OPT` 输入文件。
- 支持 OT/对角化、磁性、DFT+U、Molden、电荷分析和 cube 输出等设置。
- 支持单文件和批量 INP 生成，并可同时创建本地 Slurm 脚本。
- 载入并显示 CIF/MCIF、XYZ、PDB/ENT、GRO、GJF/COM、POSCAR/VASP 和 CP2K INP/RESTART。
- 支持晶胞、周期映射、边界双显、扩胞、原子选择、显示键编辑、视角书签、撤销/重做和高清图片导出。

### 源码结构

```text
CP2K_FORGE_EXE/
|- cp2k_forge_exe/              PyQt 桌面界面和可视化源码
|- cp2k_forge_backend/          桌面专用的稳定 INP 生成后端源码
|- CP2K_FORGE_EXE.spec          PyInstaller 构建配置
|- requirements.txt             Python 依赖
`- run.py                       桌面程序入口
```

GitHub 仓库仅保留桌面程序运行和构建所需源码及必要元数据，不包含网页端、tests、打包后的 EXE、计算工作目录、测试结构、备份、Multiwfn、VESTA 或 MolCanvas。本地开发目录中的原网页源码不受影响，只是不上传到 GitHub。

### 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- PyQt5 5.15 或更高版本
- 完整的 Multiwfn 安装目录

### 构建桌面程序

```powershell
python -m PyInstaller CP2K_FORGE_EXE\CP2K_FORGE_EXE.spec `
  --distpath CP2K_FORGE_EXE\dist `
  --workpath CP2K_FORGE_EXE\build --clean -y
```

生成的 `CP2K_FORGE.exe` 位于 `CP2K_FORGE_EXE\dist`，构建产物不提交到 GitHub。

### 项目范围

当前 GitHub 源码范围只包含本地 INP 生成和桌面可视化。SSH、远程提交、远程监控和下载功能不属于当前桌面项目。

## English

### Overview

CP2K_Forge is a Windows desktop application that creates CP2K `.inp` files through a validated Multiwfn-based generation path. It also provides PyQt molecular/crystal visualization, fixed-atom selection, batch generation, and local Slurm script generation.

Current versions:

- Desktop application: `v0.4.9`
- Stable INP generation backend: `v0.2.18`

### Features

- Generate `ENERGY`, `GEO_OPT`, and `CELL_OPT` input files.
- Configure OT/diagonalization, magnetism, DFT+U, Molden, charge analysis, cube output, and related settings.
- Generate single or batch inputs with optional local Slurm scripts.
- Load and visualize CIF/MCIF, XYZ, PDB/ENT, GRO, GJF/COM, POSCAR/VASP, and CP2K INP/RESTART structures.
- Display cells, wrap periodic atoms, duplicate boundary atoms, build supercells, select atoms, edit displayed bonds, save views, undo/redo visual operations, and export high-resolution images.

### Source Layout

```text
CP2K_FORGE_EXE/
|- cp2k_forge_exe/              PyQt desktop UI and visualization source
|- cp2k_forge_backend/          Desktop-only stable INP generation backend
|- CP2K_FORGE_EXE.spec          PyInstaller build configuration
|- requirements.txt             Python dependencies
`- run.py                       Desktop entry point
```

The GitHub repository contains only the source and metadata required to run and build the desktop application. It excludes the web application, tests, packaged executables, calculation workspaces, test structures, backups, Multiwfn, VESTA, and MolCanvas. The original local web source remains untouched; it is simply not uploaded to GitHub.

### Requirements

- Windows 10/11
- Python 3.10 or newer
- PyQt5 5.15 or newer
- A complete Multiwfn installation

### Build the Desktop Application

```powershell
python -m PyInstaller CP2K_FORGE_EXE\CP2K_FORGE_EXE.spec `
  --distpath CP2K_FORGE_EXE\dist `
  --workpath CP2K_FORGE_EXE\build --clean -y
```

The generated `CP2K_FORGE.exe` is placed in `CP2K_FORGE_EXE\dist`. Build artifacts are not committed to GitHub.

### Scope

The current GitHub source covers local INP generation and desktop visualization only. SSH access, remote submission, remote monitoring, and download workflows are outside the desktop project scope.
