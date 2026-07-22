# CP2K_FORGE_EXE 桌面源码 | Desktop Source

**作者 / Author:** Brant Li from City University of Hong Kong ([jiapeili-c@my.cityu.edu.hk](mailto:jiapeili-c@my.cityu.edu.hk))

> **Slurm 平台说明：** 当前 Slurm 脚本生成功能暂时只适用于作者使用的超算平台；如需协助修改或适配其他平台，请通过上述邮箱联系作者。
>
> **Slurm platform notice:** The current Slurm script generator is temporarily specific to the HPC platform used by the author. For assistance modifying or adapting it to another platform, contact the author at the email address above.

**Multiwfn 主页 / Homepage:** [http://sobereva.com/multiwfn](http://sobereva.com/multiwfn)

## 中文

本目录包含 CP2K_Forge `v0.4.9` 桌面程序源码：PyQt 主界面、结构可视化、设置持久化、桌面专用 INP 生成后端和 PyInstaller 构建配置。

INP 生成逻辑位于 `cp2k_forge_backend`。它从稳定后端 `v0.2.18` 提取，仅保留桌面程序所需的 Multiwfn 命令、规则归一、CP2K 修补、固定原子、slab、批量生成和本地 Slurm 逻辑，不包含网页 HTTP 服务或远程提交功能。`cp2k_forge_exe/backend_bridge.py` 是桌面 UI 的调用入口。

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

This directory contains the CP2K_Forge `v0.4.9` desktop source: the PyQt main window, structure visualization, persistent settings, desktop-only INP generation backend, and PyInstaller build configuration.

INP generation lives in `cp2k_forge_backend`. It is extracted from the validated `v0.2.18` backend and retains only the Multiwfn commands, rule normalization, CP2K patching, fixed-atom handling, slab logic, batch generation, and local Slurm logic needed by the desktop app. It contains no web HTTP service or remote-submission feature. `cp2k_forge_exe/backend_bridge.py` is the desktop UI entry point.

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
