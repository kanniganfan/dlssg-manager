<div align="center">

# DLSSG Manager

**A one-click GUI that unlocks DLSS Frame Generation on RTX 20 / 30 series cards**

[简体中文](../README.md) · [繁體中文](README.zh-TW.md) · **English**

[![Release](https://img.shields.io/badge/Release-v1.9.6-5B8CFF)](#download-and-install)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-333D52)](#download-and-install)
[![Upstream](https://img.shields.io/badge/Upstream-dlssg__for__sm86-9B7BFF)](#acknowledgements)

</div>

---

## Acknowledgements

> **The core capability of this project comes entirely from the upstream project [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86), developed and maintained by [sdli1995](https://github.com/sdli1995).**
>
> It is the upstream author's reverse engineering and packaging of DLSSG Native (a `version.dll` proxy plus SM86 / SM75 kernel routing)
> that makes DLSS Frame Generation available to RTX 20 / 30 series owners at all. This tool only stands on those shoulders,
> turning "find the game folder, pick an entry DLL, write the config, manage backups" into a GUI.
>
> **Respect and thanks to the original author.** The upstream binaries (the DLLs under `payload/`) are redistributed
> as-is and unmodified, and remain under the original author's copyright. If the upstream project helps you, please go and star it first.

### Following upstream

This tool **follows releases of the upstream project [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)**:

- when upstream ships a new version (new inference kernels, compatibility fixes, ...),
  this repository updates the runtime files under `payload/` and publishes a new release;
- the UI and detection logic also follow upstream's capability boundaries (for example new GPU support,
  changes to the generated-frame limit, or semantic changes such as the consistency tier);
- so **use the latest release** instead of staying on an old build — upstream compatibility fixes
  often decide whether a particular game launches at all.

If you notice upstream has moved on and this tool has not caught up, an issue is welcome.

All changes, version by version, are collected in [CHANGELOG.md](../CHANGELOG.md).

DLSS and DLSS Frame Generation are trademarks and proprietary technology of NVIDIA Corporation. The upstream 0.4.1 runtime pack is
redistributed exactly as officially published and includes third-party NVIDIA and Intel binaries; licensing and provenance are documented
in `payload/THIRD_PARTY_NOTICES.txt`, and this tool does not modify those files.

### Why this tool exists

Several friends I play games with are still on RTX 30 or 20 series cards. They see other people turn frame generation on and
complain that their own card "does not generate". I shared the original author's project with them — GitHub is barely reachable
here, and once it opened they stared at the page for ages and still had no idea where to start. So I dug out my old PC and built
this GUI: now they click two buttons and frame generation is on.

This tool is for them, and for everyone who was in their position back then.

---

## Screenshots

<div align="center">

<img src="screenshot.png" width="880" alt="DLSSG Manager main window">

<sub>Main window — game list on the left, detection results and frame-generation settings on the right</sub>

</div>

<details>
<summary><b>More screenshots</b> (consistency tier / English UI / narrow window)</summary>

<br>

**Consistency tier (added in upstream 0.3.2)** — four levels, selectable 0–3:

<div align="center">
<img src="screenshot_tier.png" width="620" alt="Consistency tiers 0 to 3">
</div>

**English UI**:

<div align="center">
<img src="screenshot_en.png" width="820" alt="English UI">
</div>

**Narrow window (820×900)** — setting rows wrap automatically, content scrolls, nothing is clipped or overlapping:

<div align="center">
<img src="screenshot_narrow.png" width="620" alt="Narrow window layout">
</div>

</details>

---

## What it is

DLSSG Manager scans your installed D3D12 games, locates the real rendering executable,
and deploys or reverts the upstream DLSSG proxy and configuration in one click, so RTX 20 (SM75) / RTX 30 (SM86)
cards can enable **frame generation** in games that already support DLSS.

### Features

- **Automatic game detection**: Steam / Epic / GOG / Ubisoft libraries, deep scanning by drive letter, and manually added folders;
  it looks through launchers to find the real rendering executable and recognises Unreal / Unity titles
- **Smoother startup and scanning**: the splash animation reuses the static background, while GPU detection and runtime-pack validation run in the background; game folders are analysed with up to 4 workers and results keep their original order
- **One-click enable / one-click restore**: the entry DLL gets out of the way automatically (version → winmm → dbghelp → dinput8)
  and never overwrites someone else's file; deployment verifies SHA-256 and backs up originals, restore puts everything back
- **Consistency tier (0–3)**: how far the generated image may deviate from the official runtime —
  `0` factory kernels (most conservative), `1` fully bit-exact acceleration (default, **image identical to official**),
  `2` adds lossy image kernels, `3` all-lossy acceleration (fastest)
- **Two frame-generation engines**: DLSS-G by default; optional XeSS-FG multi-frame generation (2X–4X)
- **DLSS Super Resolution options**: M/L INT8 or FP16 kernels, off by default, available on RTX 20 / 30 series
- **Self-explanatory settings**: hover to read what the DLSS-G A/B/C presets and each DLSS super-resolution mode do; false positives in the scan can be removed from the card's context menu and ignored (no game files are deleted)
- **Runtime pack**: upstream 0.4.1 with the 310.9.16 runtime; DLSS-G up to 6X, XeSS-FG up to 4X, with the actual multiplier still limited by the game
- **Compatible runtime fallback**: if a game crashes with the new runtime, switch to the 310.9 or 310.1 compatible runtime (upstream 0.3.5) and redeploy; the UI hides the 0.4.x-only options and adjusts the multiplier / tier limits accordingly
- **Resolution aware**: reads UE / Unity config files to estimate the current resolution and give a VRAM budget
- **Anti-cheat notice**: when an anti-cheat system is detected, the tool only warns you; no feature is blocked
- **System preparation**: detects the Hardware-accelerated GPU scheduling (HAGS) setting, with a one-click toggle and a shortcut to the Windows setting, for steadier frame times
- **Entry DLL layering mirrors upstream**: utility proxies first (`version` → `winmm` → `dbghelp` → `dinput8`, the only set auto-selection uses);
  `dxgi` / `d3d12` sit on the D3D12 render hot path and are load-order sensitive, so they are listed as high risk, must be chosen manually, and are **mutually exclusive** (enforced at deploy time)
- **GPU name masking**: presents the card as an RTX 40 / 50 series model (50 / 60 / 70 / 80 / 90 and Ti tiers)
  to get past games that gate on the model number; custom names are supported and everything can be restored in one click.
  The name is written to the Windows "device instance" name (what DXGI / WMI read) and a **one-click GPU restart** applies it immediately
- **Update check**: silently checks for a new version at startup (at most once every 6 hours) and shows a clickable badge in the title bar
  when one exists; there is also a "Check for updates" button in the footer. **It only reads the public API and uploads no local data**
- **Localisation**: Simplified Chinese / Traditional Chinese / English, chosen automatically from the system language;
  the community can drop extra language files into `lang/` without repackaging
- **Polished UI**: borderless rounded dark theme, KANNI loading animation, macOS-style three-colour window buttons, pixel-accurate text ellipsis

---

## Download and install

Go to the [**Releases**](../../releases) page and download the build you want (current **v1.9.6**):

| Edition | File | Who it is for |
|---|---|---|
| **Portable** | `DLSSG_Manager_1.9.6_portable_x64.zip` | Unzip and run, writes nothing to the registry |
| **Installer** | `DLSSG_Manager_1.9.6_setup_x64.exe` | Wants a setup wizard, Start menu / desktop shortcuts and a full uninstall |

**Portable**: extract to any folder and double-click `DLSSG Manager.exe`.
**Installer**: run the setup, pick a folder; to uninstall use "Settings → Apps → Installed apps" or the
Uninstall entry in the Start menu — shortcuts and registry entries are removed as well.

> Both editions are functionally identical and ship with the `payload/` runtime and the language files,
> so **you do not need Python, CUDA or any other runtime** (a 2–4 second first launch while it unpacks is normal).

---

## Usage

1. The app scans your games on startup (or use "Deep scan" to sweep a whole drive, or "Add game folder manually...").
2. Select a game on the left and check the detection results on the right (render process, resolution, anti-cheat notice, deployment state).
3. Pick the frame-generation engine, multiplier and consistency tier; DLSS-G preset and super-resolution mode can be tuned as needed, and super resolution is off by default.
4. Click **"Enable frame generation"**, fully quit the game, then start it again.
5. Turn frame generation on in the game's graphics settings and choose the multiplier (DLSS-G up to 6X, XeSS-FG up to 4X).
6. To undo everything, come back and click **"Restore"**; the game folder is cleaned up.

For more detail (VRAM budget, INI parameters, troubleshooting, capability limits) see [docs/使用说明.txt](使用说明.txt) (Chinese).

### System requirements

| Item | Requirement |
|---|---|
| OS | Windows 10 2004+ (build 19041) / Windows 11, x64 |
| GPU | NVIDIA RTX 20 / 30 series (SM75 / SM86) |
| Driver | NVIDIA R580 or newer (a hard requirement of upstream 0.4.x) |
| Game | D3D12 with the DLSS runtime bundled (the tool detects and tells you) |

---

## Localisation

The UI language is switched in the **drop-down at the top right of the title bar** (restart the app to apply); the first launch follows the system language.
To add a language, create `lang/<language-code>.json` in the program folder (UTF-8, keys are the Simplified Chinese source strings, values are the translation,
plus `"_meta": {"name": "<native language name>"}`), following the bundled `lang/en_US.json`, then restart.
From the command line you can also pass `--lang en_US` for one session.

---

## Building from source

```bat
git clone https://github.com/kanniganfan/dlssg-manager.git
cd dlssg-manager
python scripts\import_upstream_release.py path\to\dlssg-release-0.4.1-x64.zip
scripts\build_windows.bat
python scripts\build_release.py --portable-only
```

First use `scripts/import_upstream_release.py` to verify the SHA-256 of the official 0.4.1 release and import it into `payload/`,
then build the app and the release packages. The published artefacts contain the full runtime pack, source licences and third-party notices.

Layout:

```
src/       Python source (core logic / UI / i18n engine / entry point)
lang/      UI language files (JSON, editable or extensible)
assets/    icon assets
docs/      usage notes and UI screenshots
scripts/   build, verification and maintenance scripts
```

The self-check scripts under `scripts/` (run before committing):

| Script | Purpose |
|---|---|
| `check_tuple_arity.py` | Verifies that constants such as `ENTRIES` / `RUNTIMES` keep a consistent tuple length |
| `check_i18n_keys.py` | Compares the keys used by `tr()` in `src/` with the dictionaries and lists missing / unused ones |
| `check_upstream_sync.py` | Checks whether upstream has a new version and verifies via git blob SHA-1 that the local payload is byte-identical to upstream HEAD (exit 0 = in sync / 1 = needs sync) |
| `smoke_ui.py` | Offscreen UI smoke test: tier wiring, `FlowRow` wrapping, toast placement, no clipped button text, three update-check states |
| `e2e_deploy.py` | Runs deploy → read back → restore in a temporary folder |
| `scan_parallel_check.py` | Checks result order, de-duplication and timing of parallel scanning on synthetic folders |
| `build_release.py` | Packages the portable zip and the NSIS installer |

---

## Limits and disclaimer

- Only **Windows x64 + D3D12** games are supported; Vulkan is not
- The multiplier ceiling depends on the engine and the game: DLSS-G up to 6X, XeSS-FG up to 4X, and most games are further limited by their built-in plugin
- XeSS-FG and super-resolution modes are optional; quality and performance depend on the game, the GPU and the resolution — DLSS-G is the default and super resolution is off
- Upstream 0.4.1's real-hardware and offline test coverage is documented in `payload/README.md`; results differ across engines, GPUs and games
- **Anti-cheat notice**: when an anti-cheat system is detected the tool only warns you; please use it only in single-player / offline / lab environments,
  and judge for yourself (and accept the consequences of) using it in online modes
- **Update check**: silently checks whether this tool has a new version at startup (at most once every 6 hours),
  or on demand via "Check for updates" in the footer; a clickable version badge appears in the title bar when one exists.
  The check is a **read-only query against the public GitHub API; it uploads no local data** and sends no identifiers
- Apart from that update check the tool never goes online and uploads nothing; everything happens on your machine
- Make sure you understand the above before changing game folders; all consequences of using this tool are the user's own

---

## Contact

- Email: [cylqm@qq.com](mailto:cylqm@qq.com)
- Email: [cao673100060@gmail.com](mailto:cao673100060@gmail.com)

Issues and PRs are welcome; language-file contributions (any language) are especially welcome.

---

## License

The code of this project is released under the [MIT License](../LICENSE).
The upstream runtime pack under `payload/` is bundled exactly as officially published; every third-party file keeps its original licence,
see `payload/LICENSE.md` and `payload/THIRD_PARTY_NOTICES.txt`. DLSS technology and trademarks belong to NVIDIA Corporation.

---

<div align="center">

**Again, all credits to [sdli1995/dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)**

</div>
