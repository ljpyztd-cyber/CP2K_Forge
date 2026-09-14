# CP2K_FORGE_EXE 桌面源码 | Desktop Source

**作者 / Author:** Brant Li from City University of Hong Kong ([jiapeili-c@my.cityu.edu.hk](mailto:jiapeili-c@my.cityu.edu.hk))

**Multiwfn 主页 / Homepage:** [http://sobereva.com/multiwfn](http://sobereva.com/multiwfn)

## 中文

本目录包含 CP2K_Forge `v0.4.11` 桌面程序源码：PyQt 主界面、结构可视化、设置持久化、桌面专用 INP 生成后端和 PyInstaller 构建配置。可视化模块支持整套结构或仅所选原子在球棍与 VDW 表示之间切换。

INP 生成逻辑位于 `cp2k_forge_backend`。它从稳定后端 `v0.2.18` 提取，仅保留桌面程序所需的 Multiwfn 命令、规则归一、CP2K 修补、固定原子、slab、批量生成和本地 Slurm 逻辑，不包含网页 HTTP 服务或远程提交功能。`cp2k_forge_exe/backend_bridge.py` 是桌面 UI 的调用入口。

电子结构菜单提供 La-Lu 镧系元素 LnPP1 功能。检测到镧系元素时自动勾选，并将 OT 最小化器初始设为 CG；用户仍可手动改回 DIIS。该功能仅修补 `&DFT` 中的数据文件引用和镧系 `&KIND` 中的基组/赝势映射，不改动 SCF 精度、截断能、MAX_SCF 或 DFT+U。运行生成的任务前，请确保 CP2K 能找到 `BASIS_MOLOPT_LnPP1` 和 `POTENTIAL+LnPP1`。

### 运行

```powershell
python -m pip install -r CP2K_FORGE_EXE\requirements.txt
python CP2K_FORGE_EXE\run.py
```

### 打包

```powershell
python -m PyInstaller CP2K_FORGE_EXE\CP2K_FORGE_EXE.spec `
  --distpath CP2K_FORGE_EXE\dist `
  --workpath CP2K_FORGE_EXE\build --clean -y
```

`dist`、`build` 和 `.exe` 文件不会提交到 GitHub。Multiwfn 为独立第三方软件，也不包含在本仓库中。使用本项目开展研究时，请遵守仓库根目录 README 中的 Multiwfn 正文引用要求。

## English

This directory contains the CP2K_Forge `v0.4.11` desktop source: the PyQt main window, structure visualization, persistent settings, desktop-only INP generation backend, and PyInstaller build configuration. The viewer can switch the complete structure or only selected atoms between ball-stick and VDW representations.

INP generation lives in `cp2k_forge_backend`. It is extracted from the validated `v0.2.18` backend and retains only the Multiwfn commands, rule normalization, CP2K patching, fixed-atom handling, slab logic, batch generation, and local Slurm logic needed by the desktop app. It contains no web HTTP service or remote-submission feature. `cp2k_forge_exe/backend_bridge.py` is the desktop UI entry point.

The electronic-structure panel provides La-Lu LnPP1 support. Detection enables it automatically and initially selects CG for the OT minimizer; users can still switch back to DIIS. It patches only the data-file references under `&DFT` and the basis/potential mappings under lanthanide `&KIND` sections. It does not change SCF accuracy, cutoffs, MAX_SCF, or DFT+U. Before running the generated task, ensure that CP2K can find `BASIS_MOLOPT_LnPP1` and `POTENTIAL+LnPP1`.

### Run

```powershell
python -m pip install -r CP2K_FORGE_EXE\requirements.txt
python CP2K_FORGE_EXE\run.py
```

### Package

```powershell
python -m PyInstaller CP2K_FORGE_EXE\CP2K_FORGE_EXE.spec `
  --distpath CP2K_FORGE_EXE\dist `
  --workpath CP2K_FORGE_EXE\build --clean -y
```

The `dist` and `build` directories and `.exe` files are not committed to GitHub. Multiwfn is independent third-party software and is not included. Research users must follow the main-text Multiwfn citation requirement in the repository root README.
