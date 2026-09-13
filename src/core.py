"""DLSSG Manager - 核心逻辑层（不依赖 Qt，可单独用 CLI 跑）

职责：
  * 自动识别本机已安装的游戏（Steam / Epic / GOG / Ubisoft / 自定义目录 / 深度全盘扫描）
  * 在游戏目录中定位真正的“渲染 EXE”，并探测 DLSS 帧生成能力与反作弊组件
  * 一键部署 / 一键恢复本项目的代理 DLL 与配置，带备份、哈希校验与权限兜底
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import winreg
except ImportError:  # 非 Windows 平台的占位，实际逻辑不会走到
    winreg = None  # type: ignore

import i18n
from i18n import tr  # 多语言：中文字面量为源键，详见 i18n.py

APP_NAME = "DLSSG Manager"
APP_VERSION = "1.2.0"
APP_TITLE = f"{APP_NAME} {APP_VERSION}"
MOD_NAME = "DLSSG Native 0.2.4"

INI_NAME = "dlssg_sm86.ini"
LOG_DIR_NAME = "dlssg_sm86"

# 入口 DLL：(内部键, 部署文件名, 包内相对路径, 说明)
ENTRIES = [
    ("version", "version.dll", "version.dll", '默认入口'),
    ("winmm", "winmm.dll", "altnative/winmm.dll", '备用入口'),
    ("dinput8", "dinput8.dll", "altnative/dinput8.dll", '备用入口'),
    ("winhttp", "winhttp.dll", "altnative/winhttp.dll", '备用入口'),
    ("dxgi", "dxgi.dll", "altnative/dxgi.dll", '备用入口'),
]

# 运行包内文件校验和（与 GitHub 仓库 main 分支一致）
PAYLOAD_SHA256 = {
    "version.dll": "c844646d835a7b88ed1382eea80403d38b433f8ac09cf92581c73698c44ae7c2",
    "altnative/winmm.dll": "1004dd4ee0edbe4e1af4c8c7b30d4786bea0f5e7c0412566996b4c2543ae7e36",
    "altnative/dinput8.dll": "ef3c3d49c5b5c8a17289c24da9b22885570793d72f3db628fa500f9efdb20489",
    "altnative/winhttp.dll": "1619839e4d1b6145ce9a587ba807f42e64f2b0984af9e81700d42ccf46ff7253",
    "altnative/dxgi.dll": "8d29eddbd7f1c3e272d07f94ab8812a80ef5b7aeb73923320bf9a432ddcf74c0",
}

# 排除的 EXE 关键字：启动器、反作弊、安装器、录制工具、崩溃上报等，不是真正渲染进程
EXE_BLACKLIST = (
    "launcher", "crash", "report", "unins", "setup", "install", "dxsetup", "dxwebsetup",
    "vcredist", "ue4prereq", "ueprereq", "unrealcefsubprocess", "epicwebhelper", "bootstrap",
    "easyanticheat", "eac", "battleye", "beservice", "anticheat", "be_", "eossdk",
    "activation", "updater", "update", "patcher", "patch", "repair", "helper", "service",
    "overlay", "unitycrashhandler", "createdump", "editor", "server", "dedicated", "benchmark",
    "gamebar", "presentmon", "capture", "record", "obs", "config", "settings", "upload",
    "start", "neac", "ccmini", "offsets", "encode", "dump", "inject", "debug", "verify",
    "probe", "tray", "aio", "unrealpak", "crashreportclient",
)

DIR_BLACKLIST = ("engine", "redist", "redistributable", "support", "__installer", "directx",
                 "dotnet", "vcredist", "backup", "tools", "sdk", "symbols", "crashreport",
                 "node_modules", "$recycle.bin", "system volume information", "appdata",
                 "programdata", "perflogs", "recovery", "msocache", "windows", "temp")

SKIP_ROOTS = {"windows", "$recycle.bin", "system volume information", "appdata", "programdata",
              "perflogs", "recovery", "msocache", "$windows.~bt", "system32"}

# 额外显存占用参考（MiB）：按最终输出分辨率与倍率
VRAM_TABLE = {
    (1920, 1080): {2: 320, 3: 330, 4: 340},
    (2560, 1440): {2: 490, 3: 510, 4: 520},
    (3840, 2160): {2: 700, 3: 740, 4: 770},
}

# 反作弊特征码：只判断「有没有」，不区分厂商/类型（产品决策：检测到仅提示，
# 不展示具体反作弊名，也不做任何限制）。
ANTICHEAT_TOKENS = (
    ("easyanticheat", "easyanticheat_eos", "eac_launcher"),
    ("battleye", "beservice", "be_service"),
    ("anticheatexpert", "ace-game", "acegame", "sguard", "ace_"),
    ("neacclient", "neacinterface", "neacsafe"),
    ("denuvo_anticheat", "denuvoanticheat"),
    ("xigncode", "xigncode3"),
)

GPU_NAME_TOKENS = [
    ("SM86", ("rtx 30", "rtx a", "a40", "a10", "a30", "a16", "a2 ", "rtx 3050", "rtx 3060",
              "rtx 3070", "rtx 3080", "rtx 3090", "cmp 170", "cmp 90")),
    ("SM75", ("rtx 20", "titan rtx", "quadro rtx", "rtx 2070", "rtx 2080", "gtx 16",
              "gtx 1650", "gtx 1660", "tesla t4", "quadro t")),
]


# ---------------------------------------------------------------- 路径工具

def app_root() -> Path:
    """程序所在目录（兼容 PyInstaller 冻结后的 exe）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def payload_dir() -> Path | None:
    """定位运行包（version.dll + altnative/）。"""
    root = app_root()
    for cand in (root / "payload", root, root.parent / "dlssg_sm86_pack"):
        if (cand / "version.dll").is_file():
            return cand
    return None


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / "DLSSGManager"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_file() -> Path:
    return data_dir() / "state.json"


def backups_dir() -> Path:
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- 基础工具

def sha256(path: Path, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def norm(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def canon_dir(p) -> str:
    """目录显示与识别的统一大小写规范：
    盘符一律大写；其余部分取磁盘上的真实大小写（resolve 走
    GetFinalPathNameByHandle，已存在的路径会返回规范大小写）。
    这样同一目录无论来自 Steam 库文件、注册表、深度扫描还是手动输入，
    识别与列表显示都一致，也不会因大小写差异产生重复条目。
    """
    if not p:
        return str(p) if p else ""
    try:
        r = str(Path(p).resolve())
    except Exception:
        r = os.path.normpath(str(p))
    if len(r) >= 2 and r[1] == ":":
        r = r[0].upper() + r[1:]
    return r


def size_text(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def run_cmd(args, timeout: int = 10) -> str:
    try:
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                             creationflags=flags, encoding="utf-8", errors="ignore")
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return ""


def read_text(path: Path, default: str = "") -> str:
    """带编码嗅探的读取：游戏配置文件编码很杂（UTF-8 / UTF-16 / GBK）。"""
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return default
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "ignore")
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return raw.decode("utf-32-le", "ignore")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "ignore")
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


# ---------------------------------------------------------------- HAGS 检测

HAGS_KEY = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
HAGS_VALUE = "HwSchMode"
HAGS_ON, HAGS_OFF = 2, 1


@dataclass
class HagsInfo:
    """硬件加速 GPU 计划（Hardware-Accelerated GPU Scheduling）状态。"""

    supported: bool = True      # 系统/驱动是否具备该能力
    enabled: bool = False       # 是否已开启
    value: int = 0              # 注册表原值，0 = 不存在
    admin: bool = False         # 当前进程是否有管理员权限
    build: int = 0              # Windows 内部版本号
    driver_ok: bool = True
    reason: str = ""            # 不支持时的原因
    source: str = ""            # 状态来源：注册表 / 设置

    @property
    def needs_reboot_hint(self) -> bool:
        return self.supported and not self.enabled

    def summary(self) -> str:
        if not self.supported:
            return tr('不可用（{0}）').format(self.reason) if self.reason else tr('不可用')
        return tr('已开启') if self.enabled else tr('未开启')


_HAGS_CACHE: HagsInfo | None = None
_MASK_CACHE: "GpuMaskInfo | None" = None


def _windows_build() -> int:
    try:
        return int(winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"),
            "CurrentBuildNumber")[0])
    except Exception:
        try:
            return sys.getwindowsversion().build
        except Exception:
            return 0


def hags_supported(build: int) -> tuple[bool, str]:
    if os.name != "nt":
        return False, tr('非 Windows 系统')
    if build and build < 19041:
        return False, tr('Windows 版本过低（build {0}，需 2004 / build 19041 及以上）').format(build)
    return True, ""


def detect_hags(force: bool = False) -> HagsInfo:
    """读取 HAGS 注册表状态（带缓存）。任何异常都退回「未知但可用」。"""
    global _HAGS_CACHE
    if _HAGS_CACHE is not None and not force:
        return _HAGS_CACHE

    info = HagsInfo()
    info.build = _windows_build()
    info.admin = is_admin()

    if info.build and info.build < 19041:
        info.supported = False
        info.reason = tr('需要 Win10 2004+（当前 build {0}）').format(info.build)

    val = 0
    src = tr('注册表')
    if os.name == "nt":
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, HAGS_KEY) as k:
                val = int(winreg.QueryValueEx(k, HAGS_VALUE)[0])
        except FileNotFoundError:
            val = 0                       # 值不存在 = 默认关闭
        except Exception:
            val = 0
            src = tr('读取失败')
    else:
        src = tr('非 Windows')

    info.value = val
    info.enabled = (val == HAGS_ON)
    info.source = src

    if info.supported and info.build >= 22621 and val == 0:
        # Win11 22H2+ 起该开关有独立设置存储，注册表可能缺省
        info.enabled = False
    _HAGS_CACHE = info
    return info


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def set_hags(enable: bool) -> tuple[bool, str]:
    """写入 HAGS 注册表值。返回 (是否成功, 说明)。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统，无法设置')
    want = HAGS_ON if enable else HAGS_OFF
    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, HAGS_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
            prev, _t = None, None
            try:
                prev = winreg.QueryValueEx(k, HAGS_VALUE)[0]
            except Exception:
                prev = None
            winreg.SetValueEx(k, HAGS_VALUE, 0, winreg.REG_DWORD, want)
        detect_hags(force=True)
        old = tr('未设置') if prev is None else (tr('开启') if int(prev) == HAGS_ON else tr('关闭'))
        return True, tr('已{0}（原状态：{1}），重启后生效').format('开启' if enable else '关闭', old)
    except PermissionError:
        return False, tr('需要管理员权限才能修改系统设置')
    except Exception as e:
        return False, tr('写入失败：{0}: {1}').format(type(e).__name__, e)


def hags_cli_text(info: HagsInfo | None = None) -> str:
    info = info or detect_hags(force=True)
    return (f"HAGS: {info.summary()} | value={info.value} | build={info.build} "
            f"| admin={info.admin} | supported={info.supported}")


# ---------------------------------------------------------------- 显卡伪装
#
# 原理：Windows 显示适配器的「友好名称」存在注册表 Class 键下，游戏/DLSS 初始化
# 时会读它来判断显卡型号。把 DriverDesc / AdapterString / ChipType 改成更高的型号
# （如 RTX 4060），部分按型号白名单判断的游戏就会允许开启帧生成。
#
# 注意：
# - 只改「名称字符串」，不动 MatchingDeviceId / 硬件 ID —— 驱动匹配不受影响；
# - 必须管理员权限（HKLM）；
# - 改完需重启（或重启显卡驱动）才生效；
# - 原值保存在 state.json 里，可一键还原。

GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
GPU_NAME_VALUES = ("DriverDesc", "HardwareInformation.AdapterString",
                   "HardwareInformation.ChipType")

# 伪装前缀（默认 40/50 系）
MASK_PREFIXES = ["RTX 40", "RTX 50"]
# 后缀档位
MASK_SUFFIXES = ["50", "50 Ti", "60", "60 Ti", "70", "70 Ti", "80", "80 Ti", "90", "90 Ti"]


@dataclass
class GpuMaskInfo:
    """显卡伪装状态。"""

    supported: bool = True
    admin: bool = False
    adapter_key: str = ""          # 注册表子键，如 ...\0000
    original: str = ""             # 原始显卡名
    current: str = ""              # 当前注册表里的名字
    masked: bool = False           # 是否处于伪装状态
    reason: str = ""               # 不可用原因


def _gpu_class_subkeys() -> list[str]:
    """列出 Class 下的数字子键（0000/0001…），失败返回空。"""
    out: list[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_CLASS_KEY) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                sub = winreg.EnumKey(k, i)
                if sub.isdigit():
                    out.append(sub)
    except Exception:
        pass
    return out


def _find_nvidia_subkey() -> str:
    """找到 NVIDIA 显卡所在的 Class 子键。"""
    for sub in _gpu_class_subkeys():
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                f"{GPU_CLASS_KEY}\\{sub}") as k:
                desc = str(winreg.QueryValueEx(k, "DriverDesc")[0])
                prov = str(winreg.QueryValueEx(k, "ProviderName")[0]) \
                    if _has_value(k, "ProviderName") else ""
            if "nvidia" in desc.lower() or "nvidia" in prov.lower():
                return sub
        except Exception:
            continue
    return ""


def _has_value(key, name: str) -> bool:
    try:
        winreg.QueryValueEx(key, name)
        return True
    except Exception:
        return False


def _read_gpu_names(sub: str) -> dict[str, str]:
    """读取子键下的三个名称值。"""
    vals: dict[str, str] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            f"{GPU_CLASS_KEY}\\{sub}") as k:
            for n in GPU_NAME_VALUES:
                try:
                    v = winreg.QueryValueEx(k, n)[0]
                    vals[n] = v if isinstance(v, str) else str(v)
                except Exception:
                    pass
    except Exception:
        pass
    return vals


def detect_gpu_mask(force: bool = False) -> GpuMaskInfo:
    """检测当前显卡伪装状态。"""
    global _MASK_CACHE
    if _MASK_CACHE is not None and not force:
        return _MASK_CACHE

    info = GpuMaskInfo()
    info.admin = is_admin()
    if os.name != "nt":
        info.supported = False
        info.reason = tr('非 Windows 系统')
        _MASK_CACHE = info
        return info

    sub = _find_nvidia_subkey()
    if not sub:
        info.supported = False
        info.reason = tr('未找到 NVIDIA 显卡的注册表项')
        _MASK_CACHE = info
        return info

    info.adapter_key = sub
    names = _read_gpu_names(sub)
    info.current = names.get("DriverDesc", "")

    # 原始名称从 state 读取；state 里没有说明从未伪装过，当前名即原始名
    st = load_state()
    rec = st.get("gpu_mask") or {}
    info.original = rec.get("original") or info.current
    info.masked = bool(rec.get("masked")) and bool(rec.get("original"))

    # 交叉校验：当前名与记录不符，说明被外部改过
    if info.masked and info.current and info.original \
            and info.current == info.original:
        # 记录说伪装了但名字是原始的 -> 可能已手动还原
        info.masked = False
    _MASK_CACHE = info
    return info


def build_mask_name(prefix: str, suffix: str) -> str:
    """拼出伪装名称。

    支持：
      ("RTX 40", "60")      -> NVIDIA GeForce RTX 4060
      ("RTX 50", "80 Ti")   -> NVIDIA GeForce RTX 5080 Ti
      ("", "4090")          -> NVIDIA GeForce RTX 4090   （纯数字自动补 RTX）
      ("", "RTX 4090")      -> NVIDIA GeForce RTX 4090
      ("", "NVIDIA ...")    -> 原样使用
    """
    prefix = (prefix or "").strip()
    suffix = (suffix or "").strip()
    if not prefix and not suffix:
        return ""
    core_name = f"{prefix}{suffix}".replace("  ", " ").strip()
    if not core_name:
        return ""
    up = core_name.upper()
    if up.startswith("NVIDIA"):
        return core_name
    if up.startswith("GEFORCE"):
        return f"NVIDIA {core_name}"
    # 纯数字或形如 "4090 Ti" 的后缀 -> 补 RTX
    if core_name[0].isdigit() or up.startswith("RTX"):
        core_name = core_name if up.startswith("RTX") else f"RTX {core_name}"
    return f"NVIDIA GeForce {core_name}"


def apply_gpu_mask(prefix: str, suffix: str) -> tuple[bool, str]:
    """写入伪装名称。返回 (是否成功, 说明)。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统，无法设置')
    new_name = build_mask_name(prefix, suffix)
    if not new_name or new_name.endswith("GeForce"):
        return False, tr('请先选择要伪装的显卡型号')

    info = detect_gpu_mask(force=True)
    if not info.supported or not info.adapter_key:
        return False, info.reason or tr('未找到 NVIDIA 显卡的注册表项')

    st = load_state()
    rec = st.get("gpu_mask") or {}
    # 首次伪装时记下原始名；已伪装过则沿用最初的原始名
    original = rec.get("original") or info.current
    if not original:
        return False, tr('无法读取当前显卡名称')

    key = f"{GPU_CLASS_KEY}\\{info.adapter_key}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0,
                            winreg.KEY_SET_VALUE) as k:
            for n in GPU_NAME_VALUES:
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, new_name)
        st["gpu_mask"] = {"original": original, "masked": True,
                          "name": new_name, "prefix": prefix, "suffix": suffix}
        save_state(st)
        detect_gpu_mask(force=True)
        return True, tr('已伪装为 {0}（原 {1}），重启电脑后生效').format(new_name, original)
    except PermissionError:
        return False, tr('需要管理员权限才能修改显卡注册表')
    except Exception as e:
        return False, tr('写入失败：{0}: {1}').format(type(e).__name__, e)


def restore_gpu_mask() -> tuple[bool, str]:
    """还原原始显卡名称。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统，无法设置')
    info = detect_gpu_mask(force=True)
    if not info.supported or not info.adapter_key:
        return False, info.reason or tr('未找到 NVIDIA 显卡的注册表项')

    st = load_state()
    rec = st.get("gpu_mask") or {}
    original = rec.get("original") or ""
    if not original:
        return False, tr('没有可还原的原始显卡名称记录')

    key = f"{GPU_CLASS_KEY}\\{info.adapter_key}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0,
                            winreg.KEY_SET_VALUE) as k:
            for n in GPU_NAME_VALUES:
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, original)
        st["gpu_mask"] = {"original": original, "masked": False}
        save_state(st)
        detect_gpu_mask(force=True)
        return True, tr('已还原为 {0}，重启电脑后生效').format(original)
    except PermissionError:
        return False, tr('需要管理员权限才能修改显卡注册表')
    except Exception as e:
        return False, tr('还原失败：{0}: {1}').format(type(e).__name__, e)


def gpu_mask_cli_text(info: GpuMaskInfo | None = None) -> str:
    info = info or detect_gpu_mask(force=True)
    return (f"GPU_MASK: supported={info.supported} admin={info.admin} "
            f"masked={info.masked} current={info.current!r} "
            f"original={info.original!r} key={info.adapter_key!r}")


# ---------------------------------------------------------------- 显卡探测

@dataclass
class GpuInfo:
    name: str = '未检测到 NVIDIA 显卡'
    driver: str = ""
    vram_mb: int = 0
    route: str = "SM86"
    supported: bool = True
    note: str = ""


def detect_gpu() -> GpuInfo:
    info = GpuInfo()
    raw = run_cmd(["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                   "--format=csv,noheader,nounits"])
    if raw.strip():
        parts = [p.strip() for p in raw.strip().splitlines()[0].split(",")]
        if parts and parts[0]:
            info.name = parts[0]
            info.driver = parts[1] if len(parts) > 1 else ""
            if len(parts) > 2:
                try:
                    info.vram_mb = int(float(parts[2]))
                except ValueError:
                    info.vram_mb = 0
    else:
        ps = ("(Get-CimInstance Win32_VideoController | Where-Object {$_.Name -like '*NVIDIA*'}"
              " | Select-Object -First 1 -ExpandProperty Name)")
        out = run_cmd(["powershell", "-NoProfile", "-Command", ps])
        if out.strip():
            info.name = out.strip().splitlines()[0].strip()

    low = info.name.lower()
    route = None
    for r, tokens in GPU_NAME_TOKENS:
        if any(t in low for t in tokens):
            route = r
            break
    if route:
        info.route = route
        info.note = tr("Ampere（SM86）") if route == "SM86" else tr("Turing（SM75）")
    elif "rtx 4" in low or "rtx 5" in low:
        info.route, info.supported = "SM86", False
        info.note = tr('Ada / Blackwell 原生支持帧生成，无需本 Mod')
    else:
        info.route, info.supported = "SM86", False
        info.note = tr('非 SM86/SM75 目标架构，结果不受保证')
    if info.name == tr('未检测到 NVIDIA 显卡'):
        info.supported = False
        info.note = tr('未检测到 NVIDIA 驱动，路由需手动确认')
    return info


def vram_hint(width: int, height: int, mult: int) -> tuple[int, str] | None:
    """按输出分辨率与倍率给出额外显存估算。"""
    if not width or not height:
        return None
    pix = width * height
    best = min(VRAM_TABLE.keys(), key=lambda k: abs(k[0] * k[1] - pix))
    if abs(best[0] * best[1] - pix) / pix > 0.35:
        return None
    label = {1920: "1080p", 2560: "1440p", 3840: "4K"}.get(best[0], f"{best[0]}×{best[1]}")
    return VRAM_TABLE[best].get(mult), label


# ---------------------------------------------------------------- 数据结构

@dataclass
class Candidate:
    exe: str = ""
    exe_dir: str = ""
    engine: str = ""
    score: int = 0
    size_mb: float = 0.0
    dlssg: bool = False
    dlss: bool = False
    note: str = ""


@dataclass
class Game:
    gid: str = ""
    name: str = ""
    source: str = ""
    install_dir: str = ""
    exe: str = ""
    exe_dir: str = ""
    engine: str = ""
    dlssg: bool = False
    dlss: bool = False
    anticheat: bool = False
    candidates: list = field(default_factory=list)
    deployed: bool = False
    entry: str = ""
    installed_at: float = 0.0
    resolution: tuple = (0, 0)
    config: dict = field(default_factory=dict)


# ---------------------------------------------------------------- 启动器库扫描

def _registry_steam_path() -> list[str]:
    paths = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            v = winreg.QueryValueEx(k, name)[0]
                            if v:
                                paths.append(os.path.normpath(v))
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass
    return paths


def scan_steam() -> list[tuple[str, str, str]]:
    found = []
    roots = _registry_steam_path()
    roots += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
              r"D:\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary", r"F:\SteamLibrary"]
    libs: list[Path] = []
    for r in roots:
        rp = Path(r)
        if not rp.is_dir():
            continue
        if (rp / "steamapps").is_dir():
            libs.append(rp)
        vdf = rp / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            for m in re.finditer(r'"path"\s*"([^"]+)"', read_text(vdf)):
                p = Path(m.group(1).replace("\\\\", "\\"))
                if (p / "steamapps").is_dir():
                    libs.append(p)
    seen = set()
    for lib in libs:
        try:
            acfs = sorted((lib / "steamapps").glob("appmanifest_*.acf"))
        except OSError:
            continue
        for acf in acfs:
            if norm(acf) in seen:
                continue
            seen.add(norm(acf))
            txt = read_text(acf)
            m_name = re.search(r'"name"\s*"([^"]*)"', txt)
            m_dir = re.search(r'"installdir"\s*"([^"]*)"', txt)
            if not (m_name and m_dir):
                continue
            gdir = lib / "steamapps" / "common" / m_dir.group(1)
            if gdir.is_dir():
                found.append((m_name.group(1), str(gdir), "Steam"))
    return found


def scan_epic() -> list[tuple[str, str, str]]:
    found = []
    bases = [Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" /
             "EpicGamesLauncher" / "Data" / "Manifests"]
    for base in bases:
        if not base.is_dir():
            continue
        for item in base.glob("*.item"):
            try:
                data = json.loads(read_text(item))
            except Exception:
                continue
            name = data.get("DisplayName") or data.get("AppName") or ""
            loc = data.get("InstallLocation") or ""
            if name and loc and Path(loc).is_dir():
                found.append((name, loc, "Epic"))
    return found


def scan_gog() -> list[tuple[str, str, str]]:
    found = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games"),
                          (winreg.HKEY_CURRENT_USER, r"SOFTWARE\GOG.com\Games")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sk:
                                name = winreg.QueryValueEx(sk, "gameName")[0]
                                path = winreg.QueryValueEx(sk, "path")[0]
                                if path and Path(path).is_dir():
                                    found.append((name, path, "GOG"))
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass
    return found


def scan_ubisoft() -> list[tuple[str, str, str]]:
    found = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Ubisoft\Launcher\Installs")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sk:
                                d = winreg.QueryValueEx(sk, "InstallDir")[0]
                                if d and Path(d).is_dir():
                                    found.append((tr('Ubisoft 游戏 {0}').format(winreg.EnumKey(k, i)), d, "Ubisoft"))
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass
    return found


def _root_is_game_dir(rp: Path) -> bool:
    """判断用户添加的目录本身就是一个游戏目录，而不是装着多个游戏的库目录。"""
    try:
        for p in rp.iterdir():
            if p.is_file() and p.suffix.lower() == ".exe":
                return True
    except OSError:
        pass
    return any((rp / m).is_dir() for m in ("Binaries", "Engine", "Content", "Data", "Saved"))


def scan_custom_roots(roots: list[str]) -> list[tuple[str, str, str]]:
    found = []
    for r in roots:
        rp = Path(r)
        if not rp.is_dir():
            continue
        if _root_is_game_dir(rp):
            found.append((rp.name, str(rp), tr('自定义')))
            continue
        try:
            for child in sorted(rp.iterdir()):
                if child.is_dir():
                    found.append((child.name, str(child), tr('自定义')))
        except OSError:
            continue
    return found


# ---------------------------------------------------------------- 渲染 EXE 定位

def _exe_blacklisted(p: Path) -> bool:
    low = p.name.lower()
    if any(b in low for b in EXE_BLACKLIST):
        return True
    return bool({x.lower() for x in p.parts} & set(DIR_BLACKLIST))


def _probe_libs(root: Path, max_depth: int = 10) -> tuple[bool, bool, list[str]]:
    """探测游戏包内是否带 DLSS / DLSSG 运行库。"""
    dlssg = dlss = False
    hits: list[str] = []
    base = len(root.parts)
    try:
        for cur, dirs, files in os.walk(root):
            if len(Path(cur).parts) - base >= max_depth:
                dirs[:] = []
            low = {f.lower() for f in files}
            if "nvngx_dlssg.dll" in low:
                dlssg = True
                hits.append(cur)
            if low & {"nvngx_dlss.dll", "nvngx_dlssd.dll"}:
                dlss = True
            if dlssg and dlss:
                break
    except Exception:
        pass
    return dlssg, dlss, hits


def find_candidates(game_dir: str, max_depth: int = 8, budget: int = 600) -> list[Candidate]:
    root = Path(game_dir)
    if not root.is_dir():
        return []
    exes: list[Path] = []
    base_depth = len(root.parts)
    try:
        for cur, dirs, files in os.walk(root):
            if len(Path(cur).parts) - base_depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if d.lower() not in DIR_BLACKLIST]
            for f in files:
                if f.lower().endswith(".exe"):
                    p = Path(cur) / f
                    if not _exe_blacklisted(p):
                        exes.append(p)
            if len(exes) > budget:
                break
    except Exception:
        pass

    has_dlssg, has_dlss, dlssg_dirs = _probe_libs(root)
    name_tokens = {t for t in re.split(r"[^a-z0-9]+", root.name.lower()) if len(t) > 2}
    dlssg_dirs = {norm(d) for d in dlssg_dirs}

    out: list[Candidate] = []
    for exe in exes:
        try:
            size_mb = exe.stat().st_size / (1024 * 1024)
        except OSError:
            continue
        name = exe.name.lower()
        parent = str(exe.parent).lower()
        is_shipping = ("-win64-shipping" in name)
        if size_mb < 3 and not is_shipping:
            continue  # 渲染进程不会这么小

        score = 0
        if is_shipping:
            score += 60
        if "binaries" in parent and "win64" in parent:
            score += 35
        elif "binaries" in parent:
            score += 20
        if exe.parent == root:
            score -= 10
        try:
            near = {p.name.lower() for p in exe.parent.iterdir() if p.is_file()}
        except OSError:
            near = set()
        if "nvngx_dlssg.dll" in near:
            score += 30
        if near & {"nvngx_dlss.dll", "nvngx_dlssd.dll"}:
            score += 10
        if norm(exe.parent) in dlssg_dirs:
            score += 10
        if (exe.parent / INI_NAME).is_file() or (exe.parent / LOG_DIR_NAME).is_dir():
            score += 5
        if size_mb > 20:
            score += 18
        if size_mb > 100:
            score += 12
        stem_tokens = {t for t in re.split(r"[^a-z0-9]+", exe.stem.lower()) if len(t) > 2}
        if name_tokens & stem_tokens:
            score += 25

        if score < 30:
            continue
        out.append(Candidate(exe=str(exe), exe_dir=str(exe.parent),
                             engine="Unreal Engine" if is_shipping else tr('原生'),
                             score=score, size_mb=round(size_mb, 1),
                             dlssg=has_dlssg, dlss=has_dlss))
    out.sort(key=lambda c: (-c.score, len(c.exe_dir)))
    return out[:15]


def detect_anticheat(game_dir: str, max_depth: int = 5) -> bool:
    """只判断目录里是否出现反作弊特征文件，不识别具体类型。"""
    root = Path(game_dir)
    if not root.is_dir():
        return False
    base = len(root.parts)
    try:
        for cur, dirs, files in os.walk(root):
            if len(Path(cur).parts) - base >= max_depth:
                dirs[:] = []
            blob = " ".join([f.lower() for f in files] + [d.lower() for d in dirs])
            if any(t in blob for tokens in ANTICHEAT_TOKENS for t in tokens):
                return True
    except Exception:
        pass
    return False


def guess_resolution(exe_dir: str, game_name: str = "", exe_path: str = "") -> tuple[int, int]:
    """先读 UE 配置文件，再读 Unity 注册表，尽量拿到游戏当前分辨率。"""
    p = Path(exe_dir)
    project = ""
    for parent in list(p.parents)[:3]:
        if parent.name.lower() == "binaries":
            project = parent.parent.name.replace("-Win64-Shipping", "")
            break
    if not project:
        project = p.parent.name
    la = Path(os.environ.get("LOCALAPPDATA") or "")
    key = re.sub(r"[^a-z0-9]", "", project.lower())

    if str(la) and la.is_dir():
        for cand in (la / project, la / (project + "Game"), la / (project + "Client")):
            res = _read_ue_resolution(cand)
            if res[0]:
                return res
        try:
            children = list(la.iterdir())
        except Exception:
            children = []
        for child in children:
            try:
                if not child.is_dir():
                    continue
                cand_key = re.sub(r"[^a-z0-9]", "", child.name.lower())
                if not cand_key:
                    continue
                if key and (key in cand_key or cand_key in key
                            or (len(key) > 6 and cand_key.startswith(key[:8]))):
                    res = _read_ue_resolution(child)
                    if res[0]:
                        return res
            except OSError:
                continue

    hints = []
    for h in (Path(exe_path).stem if exe_path else "", game_name, Path(exe_dir).parent.name):
        h = re.sub(r"[^a-z0-9]", "", (h or "").lower())
        if len(h) >= 4:
            hints.append(h)
    if key:
        hints.append(key)
    return _read_unity_resolution(hints)


def _read_unity_resolution(hints: list[str]) -> tuple[int, int]:
    """Unity 游戏把分辨率记在 HKCU\\Software\\<厂商>\\<产品> 下。"""
    try:
        import winreg
    except Exception:
        return (0, 0)
    skip = {"microsoft", "policies", "classes", "wow6432node", "clients",
            "registeredapplications", "nvidia corporation", "intel", "valve", "classes"}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software") as root:
            companies = []
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    companies.append(winreg.EnumKey(root, i))
                except OSError:
                    break
    except OSError:
        return (0, 0)

    for comp in companies:
        if comp.lower() in skip:
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\" + comp) as ck:
                products = []
                for j in range(winreg.QueryInfoKey(ck)[0]):
                    try:
                        products.append(winreg.EnumKey(ck, j))
                    except OSError:
                        break
                for prod in products:
                    pl = re.sub(r"[^a-z0-9]", "", prod.lower())
                    if len(pl) < 3 or not any(h in pl or pl in h for h in hints):
                        continue
                    vals = {}
                    try:
                        with winreg.OpenKey(ck, prod) as pk:
                            for x in range(winreg.QueryInfoKey(pk)[1]):
                                try:
                                    nm, val, _t = winreg.EnumValue(pk, x)
                                    vals[nm.lower()] = val
                                except OSError:
                                    break
                    except OSError:
                        continue
                    cur_w = cur_h = def_w = def_h = 0
                    for nm, val in vals.items():
                        if not nm.startswith("screenmanager resolution "):
                            continue
                        try:
                            v = int(val)
                        except (TypeError, ValueError):
                            continue
                        if nm.startswith("screenmanager resolution width"):
                            if "default" in nm:
                                def_w = def_w or v
                            else:
                                cur_w = cur_w or v
                        elif nm.startswith("screenmanager resolution height"):
                            if "default" in nm:
                                def_h = def_h or v
                            else:
                                cur_h = cur_h or v
                    w, h = cur_w or def_w, cur_h or def_h
                    if 640 <= w <= 16384 and 480 <= h <= 16384:
                        return (w, h)
        except OSError:
            continue
    return (0, 0)


def _read_ue_resolution(base: Path) -> tuple[int, int]:
    for ini in (base / "Saved" / "Config" / "Windows" / "GameUserSettings.ini",
                base / "Saved" / "Config" / "WindowsNoEditor" / "GameUserSettings.ini"):
        try:
            if not ini.is_file():
                continue
            txt = read_text(ini)
            mx = re.search(r"ResolutionSizeX\s*=\s*(\d+)", txt)
            my = re.search(r"ResolutionSizeY\s*=\s*(\d+)", txt)
            if mx and my:
                w, h = int(mx.group(1)), int(my.group(1))
                if 640 <= w <= 16384 and 480 <= h <= 16384:
                    return (w, h)
        except OSError:
            continue
    return (0, 0)


def list_drives() -> list[str]:
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        d = f"{letter}:\\"
        if os.path.exists(d):
            out.append(d)
    return out


def deep_scan_root(root: str, budget_sec: float = 90.0,
                   progress=None) -> list[tuple[str, str, str]]:
    """在任意目录（通常是盘符）下靠 DLSS 运行库反查游戏，能发现非平台安装的游戏。"""
    rp = Path(root)
    if not rp.is_dir():
        return []
    t0 = time.time()
    base = len(rp.parts)
    hits: list[str] = []
    try:
        for cur, dirs, files in os.walk(rp):
            if time.time() - t0 > budget_sec:
                break
            depth = len(Path(cur).parts) - base
            if depth >= 7:
                dirs[:] = []
            dirs[:] = [d for d in dirs
                       if d.lower() not in DIR_BLACKLIST and d.lower() not in SKIP_ROOTS]
            if progress and int(time.time() - t0) % 3 == 0:
                progress(tr('深度扫描中… {0}s').format(int(time.time() - t0)))
            low = {f.lower() for f in files}
            if "nvngx_dlssg.dll" in low or "nvngx_dlss.dll" in low:
                hits.append(cur)
                dirs[:] = []

    except Exception:
        pass

    out: list[tuple[str, str, str]] = []
    for h in hits:
        hp = Path(h)
        rel = hp.relative_to(rp)
        if rel.parts:
            name = rel.parts[0]
            top = rp / rel.parts[0]
        else:
            name, top = rp.name, rp
        out.append((name, str(top), tr('深度扫描')))
    return out


# ---------------------------------------------------------------- 状态

def load_state() -> dict:
    f = state_file()
    if f.is_file():
        try:
            return json.loads(read_text(f))
        except Exception:
            pass
    return {"games": {}, "roots": [], "settings": {"mult": 4, "bilinear": False, "level": 1}}


def save_state(state: dict) -> None:
    tmp = state_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_file())


def game_key(exe_dir: str) -> str:
    return hashlib.sha1(norm(exe_dir).encode("utf-8")).hexdigest()[:16]


def entry_of_deployment(exe_dir: str) -> tuple[str, bool]:
    """检查目录里是否已有本项目的部署。返回 (入口文件名, 是否确认属于本项目)。"""
    d = Path(exe_dir)
    has_ini = (d / INI_NAME).is_file()
    for _key, fname, _rel, _desc in ENTRIES:
        f = d / fname
        if f.is_file():
            try:
                if sha256(f) in set(PAYLOAD_SHA256.values()):
                    return fname, True
            except OSError:
                pass
    return ("", has_ini)


# ---------------------------------------------------------------- 部署 / 恢复

def build_ini(router: str, mult: int, bilinear: bool, level: int) -> str:
    return (
        f"; {MOD_NAME} - 由 {APP_NAME} {APP_VERSION} 生成\r\n"
        "; 修改后需要重启游戏才会生效。\r\n"
        "[Compatibility]\r\n"
        "; SM86 = Ampere (RTX 30 系)；SM75 = Turing (RTX 20/16 系)\r\n"
        f"Router={router}\r\n"
        "; PTX 由驱动 JIT，兼容性最好；Cubin 需要 GPU 与 Router 精确匹配。\r\n"
        "KernelImage=PTX\r\n"
        "; 0 = 精确输出（默认）；1 = 近似硬件双线性采样，仅 SM86 生效。\r\n"
        f"HardwareBilinear={1 if bilinear else 0}\r\n"
        "\r\n[FrameGeneration]\r\n"
        "; 上限：1=2X, 2=3X, 3=4X，实际倍率由游戏请求决定。\r\n"
        f"MaxGeneratedFrames={max(1, min(3, mult - 1))}\r\n"
        "\r\n[Logging]\r\n"
        "; 0=关闭, 1=仅错误, 2=诊断, 3=详细。\r\n"
        f"Level={level}\r\n"
    )


def payload_for_entry(entry_name: str) -> tuple[Path | None, str]:
    src = payload_dir()
    if not src:
        return None, tr('未找到运行包（payload/version.dll），请确认程序目录完整')
    for _key, fname, rel, _desc in ENTRIES:
        if fname.lower() == entry_name.lower():
            p = src / rel
            return (p, "") if p.is_file() else (None, tr('运行包缺少 {0}').format(rel))
    return None, tr('未知入口 {0}').format(entry_name)


def verify_payload() -> list[str]:
    warns = []
    src = payload_dir()
    if not src:
        return [tr('未找到运行包目录，无法部署')]
    for rel, want in PAYLOAD_SHA256.items():
        p = src / rel
        if not p.is_file():
            warns.append(tr('缺少文件 {0}').format(rel))
            continue
        try:
            got = sha256(p)
        except OSError as e:
            warns.append(tr('{0} 读取失败：{1}').format(rel, e))
            continue
        if got != want:
            warns.append(tr('{0} 哈希不符（本地 {1}… / 期望 {2}…）').format(rel, got[:12], want[:12]))
    return warns


def _entry_filename(name: str) -> str:
    """把入口键（version）或文件名（version.dll）统一成部署用的文件名。"""
    n = (name or "").strip().lower()
    if not n:
        return ""
    for key, fname, _rel, _desc in ENTRIES:
        if n in (key, fname):
            return fname
    return n if n.endswith(".dll") else ""


def pick_entry(exe_dir: str, prefer: str = "") -> tuple[str, str]:
    """挑一个可用入口：目标名已被别的程序占用时跳过，避免覆盖他人文件。"""
    order = [e[1] for e in ENTRIES]
    if prefer:
        order = [prefer] + [x for x in order if x != prefer]
    for fname in order:
        target = Path(exe_dir) / fname
        if not target.exists():
            return fname, ""
        try:
            if sha256(target) in set(PAYLOAD_SHA256.values()):
                return fname, ""  # 本项目旧部署，可直接覆盖
        except OSError:
            pass
    return "", tr('五种入口名均已被其他程序占用，可在“高级”里手动指定')


def _is_running(exe_path: str) -> bool:
    if not exe_path:
        return False
    name = Path(exe_path).name
    out = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"])
    return name.lower() in out.lower()


def deploy(game: Game, router: str, mult: int, bilinear: bool, level: int,
           prefer_entry: str = "", force: bool = False) -> tuple[bool, list[str]]:
    logs: list[str] = []
    exe_dir = Path(game.exe_dir)
    if not exe_dir.is_dir():
        return False, [tr('[错误] 目录不存在：{0}').format(exe_dir)]

    warns = verify_payload()
    logs += [tr('[警告] {0}').format(w) for w in warns]
    if any(tr('未找到运行包') in w or tr('缺少文件') in w for w in warns):
        return False, logs

    hags = detect_hags()
    if not hags.supported:
        logs.append(tr('[提示] 硬件加速 GPU 计划不可用：{0}').format(hags.reason))
    elif not hags.enabled:
        logs.append(tr('[提示] 硬件加速 GPU 计划（HAGS）未开启，插帧的帧时间稳定性可能受影响。可在软件左侧「系统准备」一键开启，或手动到「设置 → 系统 → 屏幕 → 图形设置」打开。'))

    prefer_entry = _entry_filename(prefer_entry)
    if prefer_entry and prefer_entry not in [e[1] for e in ENTRIES]:
        return False, logs + [tr('[错误] 未知入口 {0}；可选：{1}').format(prefer_entry, tr('、').join((e[1] for e in ENTRIES)))]

    entry, err = pick_entry(str(exe_dir), prefer_entry)
    if force and prefer_entry:
        entry, err = prefer_entry, ""
    if not entry:
        return False, logs + [tr('[错误] {0}').format(err)]

    src, err = payload_for_entry(entry)
    if not src:
        return False, logs + [tr('[错误] {0}').format(err)]

    if _is_running(game.exe):
        return False, logs + [tr('[错误] 游戏正在运行（{0}），请先完全退出再操作').format(Path(game.exe).name)]

    key = game_key(str(exe_dir))
    bdir = backups_dir() / key
    bdir.mkdir(parents=True, exist_ok=True)
    st = load_state()
    rec = st["games"].get(key, {})
    target = exe_dir / entry
    ini_path = exe_dir / INI_NAME

    try:
        if target.exists():
            cur = sha256(target)
            if cur not in set(PAYLOAD_SHA256.values()):
                bak = bdir / (entry + ".bak")
                shutil.copy2(target, bak)
                rec.setdefault("backups", {})[entry] = str(bak)
                logs.append(tr('[备份] 原有 {0} → {1}').format(entry, bak))
        if ini_path.exists() and not rec.get("ini_backup"):
            bak = bdir / (INI_NAME + ".bak")
            shutil.copy2(ini_path, bak)
            rec["ini_backup"] = str(bak)
            logs.append(tr('[备份] 原有 {0} → {1}').format(INI_NAME, bak))

        shutil.copy2(src, target)
        new_hash = sha256(target)
        logs.append(tr('[写入] {0} → {1}（{2}）').format(entry, target, size_text(target.stat().st_size)))
        logs.append(tr('[校验] SHA256 {0}… 与运行包一致：{1}').format(new_hash[:20], new_hash == sha256(src)))

        ini_path.write_text(build_ini(router, mult, bilinear, level), encoding="utf-8")
        logs.append(f"[配置] {INI_NAME}：Router={router}，MaxGeneratedFrames="
                    f"{max(1, min(3, mult - 1))}（{mult}X），HardwareBilinear={1 if bilinear else 0}")
    except PermissionError as e:
        return False, logs + [tr('[错误] 权限不足或被占用：{0}').format(e),
                              tr('[提示] 以管理员身份运行本程序，并确认游戏已完全退出')]
    except Exception as e:
        return False, logs + [tr('[错误] 部署失败：{0}').format(e)]

    rec.update({
        "name": game.name, "exe_dir": str(exe_dir), "exe": game.exe, "entry": entry,
        "dll_sha256": sha256(target), "installed_at": time.time(), "router": router,
        "mult": mult, "bilinear": bool(bilinear), "level": level,
        "source": game.source, "engine": game.engine, "dlssg": game.dlssg,
    })
    st["games"][key] = rec
    save_state(st)
    logs.append(tr('[完成] 已启用。重启游戏后进入画面设置，打开“帧生成”并选 2X/3X/4X'))
    return True, logs


def restore(game: Game) -> tuple[bool, list[str]]:
    logs: list[str] = []
    exe_dir = Path(game.exe_dir)
    st = load_state()
    key = game_key(str(exe_dir))
    rec = st["games"].get(key)

    if _is_running(game.exe):
        return False, [tr('[错误] 游戏正在运行（{0}），请先完全退出再操作').format(Path(game.exe).name)]

    if not rec:
        entry, ours = entry_of_deployment(str(exe_dir))
        if not ours:
            return False, [tr('[信息] 该目录没有本工具的部署记录，未做任何改动')]
        rec = {"entry": entry, "backups": {}}
    entry = rec.get("entry", "")

    removed = 0
    if entry:
        f = exe_dir / entry
        if f.is_file():
            try:
                cur = sha256(f)
                if cur == rec.get("dll_sha256") or cur in set(PAYLOAD_SHA256.values()):
                    f.unlink()
                    removed += 1
                    logs.append(tr('[移除] {0}').format(entry))
                else:
                    logs.append(tr('[跳过] {0} 已被替换为其他文件，为安全起见不删除').format(entry))
            except OSError as e:
                logs.append(tr('[错误] 无法删除 {0}：{1}').format(entry, e))

    ini = exe_dir / INI_NAME
    if ini.is_file():
        try:
            ini.unlink()
            removed += 1
            logs.append(tr('[移除] {0}').format(INI_NAME))
        except OSError as e:
            logs.append(tr('[错误] 无法删除 {0}：{1}').format(INI_NAME, e))

    for fname, bak in (rec.get("backups") or {}).items():
        b = Path(bak)
        if b.is_file():
            try:
                shutil.copy2(b, exe_dir / fname)
                logs.append(tr('[还原] {0} ← {1}').format(fname, b.name))
            except Exception as e:
                logs.append(tr('[错误] 还原 {0} 失败：{1}').format(fname, e))
    if rec.get("ini_backup") and Path(rec["ini_backup"]).is_file():
        try:
            shutil.copy2(rec["ini_backup"], ini)
            logs.append(tr('[还原] {0} ← 备份').format(INI_NAME))
        except Exception as e:
            logs.append(tr('[错误] 还原配置失败：{0}').format(e))

    if st["games"].pop(key, None):
        save_state(st)
    if removed == 0:
        logs.append(tr('[信息] 没有发现需要移除的文件'))
    logs.append(tr('[完成] 已恢复到部署前的状态；游戏自带的 DLSSG 文件未受影响'))
    return True, logs


def read_deployed_config(exe_dir: str) -> dict:
    f = Path(exe_dir) / INI_NAME
    if not f.is_file():
        return {}
    txt = read_text(f)
    cfg = {}
    for k in ("Router", "KernelImage", "HardwareBilinear", "MaxGeneratedFrames", "Level"):
        m = re.search(rf"^{k}\s*=\s*(\S+)", txt, re.M)
        if m:
            cfg[k] = m.group(1)
    return cfg


# ---------------------------------------------------------------- 汇总

def collect_games(state: dict, progress=None, extra: list[tuple[str, str, str]] | None = None,
                  deep_roots: list[str] | None = None, deep_budget: float = 75.0) -> list[Game]:
    """汇总所有来源 → 定位渲染 EXE → 返回游戏列表。"""
    rows: list[tuple[str, str, str]] = []
    for label, fn in (("Steam", scan_steam), ("Epic", scan_epic),
                      ("GOG", scan_gog), ("Ubisoft", scan_ubisoft)):
        if progress:
            progress(tr('正在扫描 {0} 游戏库…').format(label))
        try:
            rows += fn()
        except Exception:
            pass
    if state.get("roots"):
        if progress:
            progress(tr('正在扫描自定义目录…'))
        rows += scan_custom_roots(state["roots"])
    for r in deep_roots or []:
        if progress:
            progress(tr('正在深度扫描 {0} …').format(r))
        rows += deep_scan_root(r, deep_budget, progress)
    if extra:
        rows += extra

    seen, uniq = set(), []
    for name, path, source in rows:
        k = norm(path)
        if k in seen:
            continue
        seen.add(k)
        uniq.append((name, path, source))

    games: list[Game] = []
    total = len(uniq)
    for i, (name, path, source) in enumerate(uniq, 1):
        if progress and i % 2 == 0:
            progress(tr('正在分析渲染进程… {0}/{1}').format(i, total))
        cands = find_candidates(path)
        if not cands:
            continue
        best = cands[0]
        exe_dir_c = canon_dir(best.exe_dir)
        g = Game(gid=game_key(exe_dir_c), name=name, source=source,
                 install_dir=canon_dir(path),
                 exe=canon_dir(best.exe), exe_dir=exe_dir_c, engine=best.engine,
                 dlssg=best.dlssg, dlss=best.dlss,
                 candidates=[asdict(c) for c in cands])
        g.anticheat = detect_anticheat(path)
        rec = state["games"].get(g.gid)
        entry, ours = entry_of_deployment(best.exe_dir)
        g.deployed = bool(rec) and bool(entry) and ours
        g.entry = entry or (rec or {}).get("entry", "")
        g.installed_at = (rec or {}).get("installed_at", 0)
        g.config = read_deployed_config(best.exe_dir)
        g.resolution = guess_resolution(best.exe_dir, name, best.exe)
        games.append(g)

    # 去重（同一 exe_dir 只保留一次）
    dedup, seen_dir = [], set()
    for g in games:
        k = norm(g.exe_dir)
        if k in seen_dir:
            continue
        seen_dir.add(k)
        dedup.append(g)
    games = dedup

    games.sort(key=lambda g: (not g.deployed, not g.dlssg, g.name.lower()))
    return games


# ---------------------------------------------------------------- CLI

def _cli(argv: list[str]) -> int:
    def log(msg):
        print(msg, flush=True)

    def note(msg):
        print(msg, file=sys.stderr, flush=True)

    if "--lang" in argv:  # CLI 也可切语言：--lang en_US
        try:
            i18n.set_lang(argv[argv.index("--lang") + 1])
        except IndexError:
            pass

    gpu = detect_gpu()
    if "--gpu" in argv:
        print(json.dumps(asdict(gpu), ensure_ascii=False, indent=2))
        return 0

    if "--hags" in argv:
        if "--on" in argv:
            ok, msg = set_hags(True)
            log(msg)
            return 0 if ok else 1
        if "--off" in argv:
            ok, msg = set_hags(False)
            log(msg)
            return 0 if ok else 1
        info = detect_hags(force=True)
        print(json.dumps(asdict(info), ensure_ascii=False, indent=2))
        return 0

    st = load_state()
    if "--scan" in argv:
        deep = []
        if "--deep" in argv:
            deep = [argv[argv.index("--deep") + 1]] if argv.index("--deep") + 1 < len(argv) else []
        games = collect_games(st, progress=note, deep_roots=deep)
        print(json.dumps({"gpu": asdict(gpu), "payload": str(payload_dir() or ""),
                          "payload_warnings": verify_payload(),
                          "games": [asdict(g) for g in games]},
                         ensure_ascii=False, indent=2))
        return 0

    if "--install" in argv:
        target = argv[argv.index("--install") + 1]
        router = argv[argv.index("--router") + 1] if "--router" in argv else gpu.route
        mult = int(argv[argv.index("--mult") + 1]) if "--mult" in argv else 4
        entry = argv[argv.index("--entry") + 1] if "--entry" in argv else ""
        g = Game(name=Path(target).name, exe_dir=canon_dir(target))
        ok, logs = deploy(g, router, mult, "--bilinear" in argv, 1, entry, bool(entry))
        for l in logs:
            log(l)
        return 0 if ok else 1

    if "--restore" in argv:
        target = argv[argv.index("--restore") + 1]
        ok, logs = restore(Game(exe_dir=target))
        for l in logs:
            log(l)
        return 0 if ok else 1

    print(f"{APP_NAME} {APP_VERSION}")
    print("  --gpu                 显示显卡探测结果")
    print("  --hags [--on|--off]   查看 / 开启 / 关闭硬件加速 GPU 计划")
    print("  --scan [--deep <盘符>] 扫描游戏并输出 JSON")
    print("  --install <EXE目录> [--router SM86|SM75] [--mult 2|3|4] [--bilinear] [--entry <入口>]")
    print("  --restore <EXE目录>")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
