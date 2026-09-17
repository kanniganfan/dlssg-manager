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
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import winreg
except ImportError:  # 非 Windows 平台的占位，实际逻辑不会走到
    winreg = None  # type: ignore

import i18n
from i18n import tr  # 多语言：中文字面量为源键，详见 i18n.py

APP_NAME = "DLSSG Manager"
APP_VERSION = "1.7.1"
APP_TITLE = f"{APP_NAME} {APP_VERSION}"
MOD_NAME = "DLSSG SM86 0.3.2"

INI_NAME = "dlssg_sm86.ini"
LOG_DIR_NAME = "dlssg_sm86"

# 内嵌运行库版本（照搬上游两个发布包）：
#   root    = 发布根目录，nvngx_dlssg 310.9，帧倍率上限 6X
#   310.1   = 310.1/ 子目录，老版本运行库，帧倍率上限 4X
RUNTIMES = [
    ("310.9", "", "310.9 运行库（最新，支持 6X）"),
    ("310.1", "310.1/", "310.1 运行库（老版本，上限 4X）"),
]
DEFAULT_RUNTIME = "310.9"

# 入口 DLL：(内部键, 部署文件名, 包内相对路径, 说明, 分组)
# 分组照上游 alternatives/README.md：
#   tool = 工具类代理（最安全，优先用）
#   render = 渲染路径代理（D3D12 热路径，加载顺序敏感，仅前几个都不行时用）
ENTRIES = [
    ("version", "version.dll", "version.dll", '默认入口（首选）', "tool"),
    ("winmm", "winmm.dll", "alternatives/winmm.dll", '第二选择', "tool"),
    ("dbghelp", "dbghelp.dll", "alternatives/dbghelp.dll", '第三选择', "tool"),
    ("dinput8", "dinput8.dll", "alternatives/dinput8.dll", '老输入栈游戏', "tool"),
    ("dxgi", "dxgi.dll", "alternatives/dxgi.dll", '渲染路径（高风险）', "render"),
    ("d3d12", "d3d12.dll", "alternatives/d3d12.dll", '渲染路径（高风险）', "render"),
]

# 渲染路径代理互斥：dxgi 与 d3d12 只能二选一
RENDER_MUTEX = {"dxgi.dll", "d3d12.dll"}

# 当前/历史版本入口哈希（识别本项目部署）。键为"包内相对路径去掉运行库前缀"。
PAYLOAD_SHA256_LEGACY = {
    "version.dll": "c844646d835a7b88ed1382eea80403d38b433f8ac09cf92581c73698c44ae7c2",
    "altnative/winmm.dll": "1004dd4ee0edbe4e1af4c8c7b30d4786bea0f5e7c0412566996b4c2543ae7e36",
    "altnative/dinput8.dll": "ef3c3d49c5b5c8a17289c24da9b22885570793d72f3db628fa500f9efdb20489",
    "altnative/winhttp.dll": "1619839e4d1b6145ce9a587ba807f42e64f2b0984af9e81700d42ccf46ff7253",
    "altnative/dxgi.dll": "8d29eddbd7f1c3e272d07f94ab8812a80ef5b7aeb73923320bf9a432ddcf74c0",
}

# 上游 0.3.0（commit 7880d3d）的 12 个代理 DLL —— 仅用于识别最老的部署。
PAYLOAD_SHA256_030 = {
    # --- 0.3.0 310.9（根目录）---
    "version.dll": "a22d2453f25d7df3fdc0d6d683c21f01769a115439d58f1341183a75faaf8c7d",
    "alternatives/winmm.dll": "197f97e90541ae688d291ef388b1eddc0c55cb657603eb55dea2d3d178b1e384",
    "alternatives/dbghelp.dll": "10e2fe2d84b8b674e184891ca5211b01c43c6700e1c8b8c6d4969286f653bff8",
    "alternatives/dinput8.dll": "01fdd5e77e64045400a2e7b6f35f98f3403335e30cd9def0e996f78240aa65da",
    "alternatives/dxgi.dll": "ae37150fe056f3388571481ad4aaf78fad720e9b52eb7e6e1e9d2dff85df841e",
    "alternatives/d3d12.dll": "63e7c3a1ba0b10e37e1a162ccf3aa2e19a0f7359de63787585c09baffd67ad45",
    # --- 0.3.0 310.1（310.1/ 子目录）---
    "310.1/version.dll": "4646fe15a21c01d251865253f55cefd5892dd2e561ece0c8efa49ae78b5de32e",
    "310.1/alternatives/winmm.dll": "dde7ec668130b09f807338c4c594609a75349860bb5ca4428797f6ab2175b9c1",
    "310.1/alternatives/dbghelp.dll": "1537a207f6490f49373ac8164e2021e6f25bd212e4abc8564dfd8110ad3afe28",
    "310.1/alternatives/dinput8.dll": "e87a61ef84f60b58e5f3b841006992a30d8fd2998096f065b317e7126ebccd9b",
    "310.1/alternatives/dxgi.dll": "f8d823609f994861d27abf50c9cb78386202650f8da1c868eaa2a40f13feef70",
    "310.1/alternatives/d3d12.dll": "337ed97b9303192915e6edcac0310dca8817f72baa414dffa83d238cdb2ca724",
}

# 上游 0.3.1（commit f275d45）重建的全部 12 个代理 DLL。
# 相对 0.3.0：恢复 RTX 20（SM75）支持、INI 逐键回退、出厂 4X、fg_gate 诊断；
# 所有 DLL 重编译重签名，体积约 26.7~28.3 MB（0.3.0 为 17.5~19.0 MB）。
# 保留本表用于识别 v1.6.0 部署（升级时可直接覆盖，不误判为第三方文件）。
PAYLOAD_SHA256_PREV = {
    # --- 0.3.1 310.9（根目录）---
    "version.dll": "3d4c7d537a6e71e3a9d41ffc6487e054b26c56d27b7c0825d39eaa7ef0c7e86d",
    "alternatives/winmm.dll": "40eaa7dff6eb6281917eb84aa1c6e580c9e69f8736b647d28decb561f6efd7eb",
    "alternatives/dbghelp.dll": "13071d2a8cccd5a4707eedd5ccf00aee6df8b6aceba03e7c1dda9358f0f2c998",
    "alternatives/dinput8.dll": "9f77a9070a7a3277f3d7e405e49e61de7e53101e2925f75bacd9cc204e14a0da",
    "alternatives/dxgi.dll": "539138464137855f5962811588000a95897b3ddb14f5b44a197e37c3e17bd9fb",
    "alternatives/d3d12.dll": "30b48198f0cd100827037bdbe27b2a15bc050ff1c276c520ffc41705920f07b1",
    # --- 0.3.1 310.1（310.1/ 子目录）---
    "310.1/version.dll": "ca4146f76d4b176d17246d8c0e66042c57f7b25dcabea3200b33821522597211",
    "310.1/alternatives/winmm.dll": "2312e761ee589204ddf4d402c1ae36367aa73d9bcd9fdfd9bbe56c06604a63e6",
    "310.1/alternatives/dbghelp.dll": "c4679d28f69e5c99aec290725ef930a2fc58c657514f65f650efdbb0a308143c",
    "310.1/alternatives/dinput8.dll": "94767cc139f8ecb6373765cd102cc85a28601cd55101f53ae854e61a4cbf4868",
    "310.1/alternatives/dxgi.dll": "7dec971ff126f427b855d1238ff2b2ecb6ab7616c467776f882e7a4e244cc5b5",
    "310.1/alternatives/d3d12.dll": "77860075059a630a90327e417cae7db6067ff56878ddb429d5d741c813dd4995",
}

PAYLOAD_SHA256 = {
    # --- 310.9（根目录，上游 0.3.2）---
    "version.dll": "39b16f2cdb16450f0edc0e0b14231951e10954131ad9aa12037700e18dc91040",
    "alternatives/winmm.dll": "f36ced34bbcd28c09f70c0d6adad2e1f9b1659cda46a204cc01a38d1ae86da37",
    "alternatives/dbghelp.dll": "67e04932c9e1d980d6431ec626f4db21b78a1375e95de6e7e9366f58f0cb9a65",
    "alternatives/dinput8.dll": "6fe34c8c291fb5be21184076b14b52b6e01de88a263ae0d10f6daa68e0bb5d4e",
    "alternatives/dxgi.dll": "988f1da4397779fd901924d793dba967d0ffa44bfaa8f9ab25b5c5641ab93ffc",
    "alternatives/d3d12.dll": "5b36c5d068b64f7413d75d30fcfa35539da26bd75452bab2a1340baf26da0fe8",
    # --- 310.1（310.1/ 子目录，上游 0.3.2）---
    "310.1/version.dll": "a1f5e4c8c43238de5b639ef858fb67fbb1874e5e8681833bc3ffff4d3b573c50",
    "310.1/alternatives/winmm.dll": "f20bff1fa5f9a9dc6b7a35ce16fc8c743a7a34a1a47c116283b682f2260b6107",
    "310.1/alternatives/dbghelp.dll": "d17643ae2aed871a646f92ff6613e0604dedab2dc4ec8c8f7f2294f1ec9f7013",
    "310.1/alternatives/dinput8.dll": "1893acb44f84185a21a5a92b6349a2227e39cefb6a901bae1025174b5c60261a",
    "310.1/alternatives/dxgi.dll": "ecc28978ff578489ea88fbd9f1c18b566f8b5d5574003e947dfbfa66e177544c",
    "310.1/alternatives/d3d12.dll": "05a83f28c942148e75d11897cc9ea9f1f3a90613a3e0aac2eea0118a016fcc54",
}


def runtime_prefix(rt: str) -> str:
    """运行库版本 -> 包内路径前缀（310.9 为根目录，310.1 为 310.1/）。"""
    for key, prefix, _desc in RUNTIMES:
        if key == rt:
            return prefix
    return ""


def runtime_mult_cap(rt: str) -> int:
    """运行库支持的帧倍率上限：310.9 = 6，310.1 = 4。"""
    return 4 if rt == "310.1" else 6


# ---------------------------------------------------------------- 一致性档位
# 上游 0.3.2 把 [FrameGeneration] Optimized 由 0/1 两态改为 0–3 四级：
# 判据只有一条 —— 允许生成的画面偏离官方 NVIDIA 运行库多远。
#   0 = 原厂内核，不做任何加速（最保守）
#   1 = 全部「逐位一致」的加速（出厂默认；画面与官方完全相同）
#   2 = 档位 1 + 有损图像内核（对官方输出 PSNR 仍在 ~50 dB 以上）
#   3 = 全部有损加速（画质代价最大，最快）
# 档位累加且单调；档位值非法时上游回退到档位 1（写这个键的人本意是要加速）。
TIER_MIN, TIER_MAX = 0, 3
DEFAULT_TIER = 1

# 上游 0.3.2 的出厂 Optimized 值（用于「恢复出厂设置」与默认值说明）
FACTORY_OPTIMIZED = 1


def tier_cap(runtime: str) -> int:
    """该运行库实际能生效的最高档位。

    310.1 构建里没有新增的有损图像内核：文档明确写了「310.1 构建上
    2/3 等同于 1」，所以本工具在 310.1 上直接钳到 1，避免给用户
    一个看起来生效其实没有的档位。
    """
    return 1 if runtime == "310.1" else TIER_MAX


def tier_label(tier: int) -> str:
    """档位的用户可读名（同时用作 i18n 键）。"""
    return {
        0: '0 原厂（最保守）',
        1: '1 逐位一致（推荐）',
        2: '2 更快（有损，PSNR 50dB+）',
        3: '3 最快（有损）',
    }.get(int(tier), '1 逐位一致（推荐）')


def clamp_tier(tier: int, runtime: str) -> tuple[int, str]:
    """把档位钳到该运行库支持的范围内。

    返回 (档位, 原因)。原因为空串表示未被钳制；否则是以下之一：
      "invalid"      —— 值非法/越界，按上游行为回退到档位 1；
      "runtime_cap"  —— 值合法但该运行库（310.1）不支持，钳到其能力上限。
    两种原因的处置相同、但给用户的提示不同，所以必须区分开。
    """
    try:
        t = int(tier)
    except (TypeError, ValueError):
        return DEFAULT_TIER, "invalid"
    if t < TIER_MIN or t > TIER_MAX:
        # 上游行为：值非法时回退到档位 1，而非 0
        # （写这个键的人本意是要打开加速，不该被静默退回原厂）
        return DEFAULT_TIER, "invalid"
    cap = tier_cap(runtime)
    if t > cap:
        return cap, "runtime_cap"
    return t, ""


def runtime_label(rt: str) -> str:
    for key, _prefix, desc in RUNTIMES:
        if key == rt:
            return desc
    return rt


def entry_group(entry_name: str) -> str:
    """入口分组：tool（安全）/ render（渲染路径，高风险）。"""
    for _k, fname, _rel, _d, grp in ENTRIES:
        if fname.lower() == entry_name.lower():
            return grp
    return "tool"


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


def payload_search_paths() -> list[Path]:
    """按优先级列出所有会尝试的 payload 位置（供诊断输出）。

    顺序：
      1. exe 旁的 payload/            —— 安装器 / 便携包的标准布局
      2. exe 旁                       —— payload 内容直接摊在 exe 旁边
      3. 上一级的 payload/            —— exe 放在子目录里的情况
      4. 上一级的 dlssg_sm86_pack/    —— 开发期工作区
      5. %LOCALAPPDATA% 下的安装位置  —— 兜底
    """
    root = app_root()
    cands: list[Path] = [
        root / "payload",
        root,
        root.parent / "payload",
        root.parent / "dlssg_sm86_pack",
    ]
    try:
        import os
        la = os.environ.get("LOCALAPPDATA", "")
        if la:
            cands.append(Path(la) / "Programs" / "DLSSG Manager" / "payload")
            cands.append(Path(la) / "DLSSG Manager" / "payload")
    except Exception:
        pass
    seen: set[str] = set()
    out: list[Path] = []
    for c in cands:
        k = str(c).lower()
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def payload_dir() -> Path | None:
    """定位运行包（version.dll 所在目录）。"""
    for cand in payload_search_paths():
        try:
            if (cand / "version.dll").is_file():
                return cand
        except OSError:
            continue
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
# 【关键】游戏并不读 Class 键的 DriverDesc —— DXGI / WMI / 多数游戏引擎读取的是
#   HKLM\SYSTEM\CurrentControlSet\Enum\PCI\<硬件ID>\<实例ID>\DeviceDesc
# 实测验证：改该值后 WMI(win32_VideoController.Name) 立即反映新名称。
# 因此伪装必须写 Enum 键，Class 键仅作辅助同步（设备管理器显示用）。
#
# 注意 DeviceDesc 原值是 INF 间接引用（"@oem41.inf,%nvidia_dev...%;NVIDIA GeForce RTX 3050"），
# 必须替换为【字面量名称】才会被识别。

GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
GPU_ENUM_ROOT = r"SYSTEM\CurrentControlSet\Enum\PCI"
# Enum 设备实例下的名称值（DeviceDesc 是 DXGI/WMI 读取的主值）
GPU_ENUM_VALUES = ("DeviceDesc", "FriendlyName")
# Class 键下的名称值（辅助：设备管理器 / 部分工具）
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
    adapter_key: str = ""          # Class 子键，如 0000
    enum_key: str = ""             # Enum 设备实例完整路径
    original: str = ""             # 原始显卡名
    current: str = ""              # 当前生效的名字（DXGI/WMI 视角）
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
                prov = ""
                try:
                    prov = str(winreg.QueryValueEx(k, "ProviderName")[0])
                except Exception:
                    pass
            if "nvidia" in desc.lower() or "nvidia" in prov.lower():
                return sub
        except Exception:
            continue
    return ""


def _find_nvidia_enum_key() -> str:
    """定位 NVIDIA 显卡的 Enum 设备实例路径。

    返回形如 ...Enum-PCI-设备实例 路径
    """
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_ENUM_ROOT) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                dev = winreg.EnumKey(root, i)
                if "VEN_10DE" not in dev.upper():
                    continue          # 只看 NVIDIA（10DE）
                base = f"{GPU_ENUM_ROOT}\\{dev}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as dk:
                        for j in range(winreg.QueryInfoKey(dk)[0]):
                            inst = winreg.EnumKey(dk, j)
                            full = f"{base}\\{inst}"
                            # 该实例需有 DeviceDesc 且描述含 NVIDIA
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full) as ik:
                                    dd = str(winreg.QueryValueEx(ik, "DeviceDesc")[0])
                                if "nvidia" in dd.lower():
                                    return full
                            except Exception:
                                continue
                except Exception:
                    continue
    except Exception:
        pass
    return ""


def _parse_device_desc(raw: str) -> str:
    """从 DeviceDesc 提取可读名称。

    DeviceDesc 可能是 INF 间接引用格式：
        @oem41.inf,%nvidia_dev.25a2.11dc.1043%;NVIDIA GeForce RTX 3050 Laptop GPU
    取分号后那段；已是字面量则原样返回。
    """
    if not raw:
        return ""
    if raw.startswith("@") and ";" in raw:
        return raw.rsplit(";", 1)[-1].strip()
    return raw.strip()


def _read_gpu_names(sub: str) -> dict[str, str]:
    """读取 Class 子键下的名称值。"""
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


def _read_enum_name(enum_key: str) -> str:
    """读取 Enum 设备实例当前生效的名称（DXGI/WMI 视角）。"""
    if not enum_key:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_key) as k:
            raw = winreg.QueryValueEx(k, "DeviceDesc")[0]
        return _parse_device_desc(str(raw))
    except Exception:
        return ""


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

    enum_key = _find_nvidia_enum_key()
    sub = _find_nvidia_subkey()
    if not enum_key and not sub:
        info.supported = False
        info.reason = tr('未找到 NVIDIA 显卡的注册表项')
        _MASK_CACHE = info
        return info

    info.adapter_key = sub
    info.enum_key = enum_key

    # 生效名称以 Enum 为准（游戏读这里）；Enum 不可用时退回 Class
    info.current = _read_enum_name(enum_key)
    if not info.current:
        names = _read_gpu_names(sub)
        info.current = _parse_device_desc(names.get("DriverDesc", ""))

    st = load_state()
    rec = st.get("gpu_mask") or {}
    info.original = rec.get("original") or info.current
    info.masked = bool(rec.get("masked")) and bool(rec.get("original"))
    # 名称已回到原始值 -> 视为未伪装
    if info.masked and info.original and info.current == info.original:
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
    if core_name[0].isdigit() or up.startswith("RTX"):
        core_name = core_name if up.startswith("RTX") else f"RTX {core_name}"
    return f"NVIDIA GeForce {core_name}"


def _write_name_values(name: str, enum_key: str, class_sub: str,
                       logs: list[str]) -> None:
    """把名称写入 Enum 与 Class 两个位置（Enum 为主）。"""
    errs = []
    # 1) Enum 设备实例 —— 游戏读取处
    if enum_key:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_key, 0,
                                winreg.KEY_SET_VALUE) as k:
                for n in GPU_ENUM_VALUES:
                    winreg.SetValueEx(k, n, 0, winreg.REG_SZ, name)
            logs.append(tr('[写入] Enum\\DeviceDesc = {0}').format(name))
        except Exception as e:
            errs.append(f"Enum: {type(e).__name__}: {e}")
    # 2) Class 键 —— 设备管理器 / 部分工具
    if class_sub:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                f"{GPU_CLASS_KEY}\\{class_sub}", 0,
                                winreg.KEY_SET_VALUE) as k:
                for n in GPU_NAME_VALUES:
                    try:
                        winreg.SetValueEx(k, n, 0, winreg.REG_SZ, name)
                    except Exception:
                        pass      # 驱动可能不允许写个别值，不致命
            logs.append(tr('[写入] Class\\DriverDesc = {0}').format(name))
        except Exception as e:
            errs.append(f"Class: {type(e).__name__}: {e}")
    if errs:
        logs.append(tr('[警告] 部分位置写入失败：{0}').format('；'.join(errs)))


def apply_gpu_mask(prefix: str, suffix: str) -> tuple[bool, str]:
    """写入伪装名称。返回 (是否成功, 说明)。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统，无法设置')
    new_name = build_mask_name(prefix, suffix)
    if not new_name or new_name.endswith("GeForce"):
        return False, tr('请先选择要伪装的显卡型号')

    info = detect_gpu_mask(force=True)
    if not info.supported:
        return False, info.reason or tr('未找到 NVIDIA 显卡的注册表项')

    st = load_state()
    rec = st.get("gpu_mask") or {}
    original = rec.get("original") or info.current
    if not original:
        return False, tr('无法读取当前显卡名称')

    logs: list[str] = []
    try:
        _write_name_values(new_name, info.enum_key, info.adapter_key, logs)
    except PermissionError:
        return False, tr('需要管理员权限才能修改显卡注册表')
    except Exception as e:
        return False, tr('写入失败：{0}: {1}').format(type(e).__name__, e)

    st["gpu_mask"] = {"original": original, "masked": True, "name": new_name,
                      "prefix": prefix, "suffix": suffix,
                      "enum_key": info.enum_key, "class_sub": info.adapter_key}
    save_state(st)
    detect_gpu_mask(force=True)
    return True, tr('已伪装为 {0}（原 {1}），重启电脑后生效').format(new_name, original)


def restore_gpu_mask() -> tuple[bool, str]:
    """还原原始显卡名称。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统，无法设置')
    info = detect_gpu_mask(force=True)
    if not info.supported:
        return False, info.reason or tr('未找到 NVIDIA 显卡的注册表项')

    st = load_state()
    rec = st.get("gpu_mask") or {}
    original = rec.get("original") or ""
    if not original:
        return False, tr('没有可还原的原始显卡名称记录')

    logs: list[str] = []
    try:
        _write_name_values(original, info.enum_key or rec.get("enum_key", ""),
                           info.adapter_key or rec.get("class_sub", ""), logs)
    except PermissionError:
        return False, tr('需要管理员权限才能修改显卡注册表')
    except Exception as e:
        return False, tr('还原失败：{0}: {1}').format(type(e).__name__, e)

    st["gpu_mask"] = {"original": original, "masked": False}
    save_state(st)
    detect_gpu_mask(force=True)
    return True, tr('已还原为 {0}，重启电脑后生效').format(original)


def restart_gpu_device() -> tuple[bool, str]:
    """重启显卡设备，让名称改动立即生效。

    DXGI 在驱动初始化时缓存适配器名称，改注册表后不重启不会刷新
    （实测：改完立即读 DXGI 仍是旧名，重启设备后变为新名）。
    用 pnputil /restart-device 等效于禁用+启用设备，通常伴随短暂黑屏。
    """
    if os.name != "nt":
        return False, tr('非 Windows 系统')
    if not is_admin():
        return False, tr('需要管理员权限才能重启显卡设备')
    info = detect_gpu_mask(force=True)
    if not info.enum_key:
        return False, tr('未找到 NVIDIA 显卡设备实例')
    inst = info.enum_key.split("Enum\\", 1)[-1]
    try:
        r = subprocess.run(["pnputil", "/restart-device", inst],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        if r.returncode == 0:
            return True, tr('已重启显卡设备，新的显卡名称立即生效')
        return False, tr('重启设备失败：{0}').format(
            (r.stderr or r.stdout or '').strip()[:200] or f"code={r.returncode}")
    except Exception as e:
        return False, tr('重启设备失败：{0}: {1}').format(type(e).__name__, e)


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


# ---------------------------------------------------------------- 更新检测

# 发布源：本项目的 GitHub 仓库（Release 即发行产物所在处）。
# 只读取公开的 REST API，不带任何本机信息；请求是「检查更新」的唯一联网行为。
UPDATE_REPO = "kanniganfan/dlssg-manager"
UPDATE_API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_PAGE = f"https://github.com/{UPDATE_REPO}/releases/latest"
UPDATE_TIMEOUT = 8          # 秒；超时即视为检查失败，不阻塞界面
UPDATE_CACHE_HOURS = 6      # 同一版本内的静默检查间隔（小时）

# 上游 mod 的发布源（同时在界面上提示上游是否有新版本）
UPSTREAM_REPO = "sdli1995/dlssg_for_sm86"
UPSTREAM_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases/latest"
UPSTREAM_PAGE = f"https://github.com/{UPSTREAM_REPO}/releases"


@dataclass
class UpdateInfo:
    """一次更新检查的结果。"""

    ok: bool = False                 # 是否成功完成检查（网络/解析都正常）
    version: str = ""                # 远端最新版本号（已去掉前导 v）
    is_newer: bool = False           # 远端版本是否高于本机
    url: str = UPDATE_PAGE           # 下载页
    notes: str = ""                  # Release 说明（可能为空）
    published: str = ""              # 发布时间（ISO 字符串，可能为空）
    upstream_version: str = ""       # 上游 mod 的最新版本（可选）
    upstream_newer: bool = False     # 上游是否高于本机内嵌的 0.3.2
    error: str = ""                  # 失败原因（ok=False 时有值）


def parse_version(s: str) -> tuple[int, ...]:
    """把 "v1.7.1" / "1.7.1" / "0.3.2" 解析成可比较的数字元组。

    非数字段一律当 0，保证任何输入都能比较而不抛异常。
    """
    s = str(s or "").strip().lstrip("vV")
    parts: list[int] = []
    for seg in re.split(r"[.\-+]", s):
        m = re.match(r"^\d+", seg)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts) if parts else (0,)


def version_gt(a: str, b: str) -> bool:
    """a 是否比 b 新。按位比较，短的一方缺位补 0（1.7 == 1.7.0）。"""
    ta, tb = parse_version(a), parse_version(b)
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    return ta > tb


def _http_json(url: str, timeout: int = UPDATE_TIMEOUT) -> dict:
    """取一个 JSON 端点。失败时抛异常，由调用方转成用户可读的错误。"""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}/{APP_VERSION}",   # GitHub API 要求带 UA
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _short_error(e: Exception) -> str:
    """把网络异常压成一句人能看懂的短句。"""
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 404:
            return tr('发布页暂不可用（404）')
        if e.code == 403:
            return tr('请求过于频繁（403），请稍后再试')
        return tr('服务器返回 {0}').format(e.code)
    if isinstance(e, urllib.error.URLError):
        reason = str(getattr(e, "reason", "") or "")
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            return tr('连接超时')
        return tr('无法连接到网络')
    if isinstance(e, TimeoutError):
        return tr('连接超时')
    if isinstance(e, (json.JSONDecodeError, ValueError)):
        return tr('返回内容无法解析')
    return tr('检查失败：{0}').format(type(e).__name__)


def check_update(include_upstream: bool = True) -> UpdateInfo:
    """检查本工具（以及上游 mod）是否有新版本。

    只做只读 GET，不上传任何数据。任何失败都返回 ok=False + error，
    绝不抛异常 —— 调用方（后台线程）据此决定是否提示用户。
    """
    info = UpdateInfo()
    try:
        data = _http_json(UPDATE_API)
    except Exception as e:                      # noqa: BLE001 - 网络层什么都可能抛
        info.error = _short_error(e)
        return info

    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    if not tag:
        info.error = tr('发布页没有版本信息')
        return info

    info.ok = True
    info.version = tag.lstrip("vV")
    info.is_newer = version_gt(info.version, APP_VERSION)
    info.url = str(data.get("html_url") or UPDATE_PAGE)
    info.notes = str(data.get("body") or "")
    info.published = str(data.get("published_at") or "")

    if include_upstream:
        try:
            up = _http_json(UPSTREAM_API)
            utag = str(up.get("tag_name") or "").strip()
            if utag:
                info.upstream_version = utag.lstrip("vV")
                # 与内嵌 mod 版本比较（MOD_NAME 形如 "DLSSG SM86 0.3.2"）
                mod_ver = MOD_NAME.rsplit(" ", 1)[-1]
                info.upstream_newer = version_gt(info.upstream_version, mod_ver)
        except Exception:                       # noqa: BLE001 - 上游查不到不影响主流程
            pass
    return info


def update_cache_file() -> Path:
    return data_dir() / "update_check.json"


def load_update_cache() -> dict:
    f = update_cache_file()
    if f.is_file():
        try:
            return json.loads(read_text(f))
        except Exception:
            pass
    return {}


def save_update_cache(d: dict) -> None:
    try:
        f = update_cache_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(f)
    except Exception:
        pass                                     # 缓存写失败不影响功能


def should_auto_check(state: dict) -> bool:
    """是否该做一次静默检查：距上次超过缓存间隔，或上次检查的是别的版本。"""
    if not state.get("settings", {}).get("auto_update_check", True):
        return False
    c = load_update_cache()
    if c.get("app_version") != APP_VERSION:
        return True
    try:
        last = float(c.get("checked_at") or 0)
    except (TypeError, ValueError):
        return True
    return (time.time() - last) > UPDATE_CACHE_HOURS * 3600


def remember_update_check(info: UpdateInfo) -> None:
    save_update_cache({
        "app_version": APP_VERSION,
        "checked_at": time.time(),
        "remote_version": info.version,
        "is_newer": info.is_newer,
        "upstream_version": info.upstream_version,
        "upstream_newer": info.upstream_newer,
        "ok": info.ok,
    })


def open_url(url: str) -> tuple[bool, str]:
    """用系统默认浏览器打开链接。"""
    try:
        if sys.platform == "win32":
            os.startfile(url)                    # type: ignore[attr-defined]
        else:
            import webbrowser
            webbrowser.open(url)
        return True, ""
    except Exception as e:                       # noqa: BLE001
        return False, tr('无法打开链接：{0}').format(e)


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
            st = json.loads(read_text(f))
            st.setdefault("settings", {}).setdefault("auto_update_check", True)
            return st
        except Exception:
            pass
    return {"games": {}, "roots": [],
            "settings": {"mult": 4, "bilinear": False, "level": 1,
                         "auto_update_check": True}}


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
    known = _all_known_hashes()
    for item in ENTRIES:
        fname = item[1]
        f = d / fname
        if f.is_file():
            try:
                if sha256(f) in known:
                    return fname, True
            except OSError:
                pass
    return ("", has_ini)


# ---------------------------------------------------------------- 部署 / 恢复

def build_ini(router: str, mult: int, bilinear: bool, level: int,
              tier: int = DEFAULT_TIER, runtime: str = "") -> str:
    """生成 dlssg_sm86.ini（上游 0.3.2 代理模式格式）。

    router / bilinear 参数保留以兼容调用方，但代理模式的 ini 不含
    Router / KernelImage / HardwareBilinear（native 模式的键，已废弃）；
    运行库与 SM86/SM75 后端内嵌在代理 DLL 中。

    tier: 一致性档位 0–3（上游 0.3.2 的 [FrameGeneration] Optimized）。
          值越界时按上游行为回退到档位 1。
    mult: 期望倍率 2~6，ini 值 = mult-1（5 = 6X 上限，由运行库钳制）。
    """
    mult = max(2, min(6, int(mult or 2)))
    t, clamp_reason = clamp_tier(tier, runtime or DEFAULT_RUNTIME)
    tier_note = ""
    if clamp_reason == "runtime_cap":
        tier_note = ("; 注意：310.1 运行库没有有损图像内核，2/3 档等同于 1 档，"
                     "已按 1 档写入。\r\n")
    elif clamp_reason == "invalid":
        tier_note = "; 注意：档位值非法，已按上游行为回退到 1 档。\r\n"
    return (
        f"; DLSSG SM86 0.3.2 - 由 {APP_NAME} {APP_VERSION} 生成\r\n"
        "; 修改后需要重启游戏才会生效。\r\n"
        "; 本文件保留上游 0.3.2 的两个决定性开关（Optimized / MaxGeneratedFrames），\r\n"
        "; 其余诊断与兼容项取安全默认、不在此文件中，完整清单见上游 docs/INSTALL.md。\r\n"
        "[General]\r\n"
        "; 1 = 启用帧生成（内嵌 Ampere 优化版 DLSS-G 运行库）；0 = 关闭（游戏自带 DLSS-G 原样加载）。\r\n"
        "Enabled=1\r\n"
        "\r\n[FrameGeneration]\r\n"
        "; 一致性档位：允许生成的画面偏离官方运行库多远。数字越大越快、离官方画面越远。\r\n"
        ";   0 = 原厂内核，不做任何加速（最保守）\r\n"
        ";   1 = 全部逐位一致的加速（推荐，默认；画面与官方完全相同）\r\n"
        ";   2 = 档位 1 + 有损图像内核（对官方输出 PSNR 仍在 ~50 dB 以上），仅 310.9 构建\r\n"
        ";   3 = 全部有损加速（画质代价最大，最快）\r\n"
        "; 档位 2/3 不再逐位一致；310.1 构建上 2/3 等同于 1。\r\n"
        + tier_note +
        f"Optimized={t}\r\n"
        "; 生成帧上限：5 = 最高 6X（仅 310.9），3 = 最高 4X。实际倍率由游戏请求并钳到运行库支持范围。\r\n"
        f"MaxGeneratedFrames={mult - 1}\r\n"
        "\r\n[Compatibility]\r\n"
        "; DLSS-G 渲染预设（UI 重组，仅 310.9），Auto = 由游戏/驱动配置决定（默认）；A = 强制关；B = 强制开。\r\n"
        "Preset=Auto\r\n"
        "\r\n[Logging]\r\n"
        "; 0=关闭, 1=仅错误, 2=配置与能力（含 fg_gate_* 帧生成闸门诊断）, 3=内核与求值轨迹。写入下方 Directory。\r\n"
        f"Level={level}\r\n"
        "Directory=dlssg_sm86\\logs\r\n"
        "\r\n[Runtime]\r\n"
        "; Bundled = 始终使用内嵌的配套运行库与后端（常规用法）。\r\n"
        "Mode=Bundled\r\n"
        "CacheDirectory=\r\n"
    )


def payload_for_entry(entry_name: str, runtime: str = "") -> tuple[Path | None, str]:
    """按入口名 + 运行库版本解析 payload 内的源文件路径。"""
    src = payload_dir()
    if not src:
        return None, tr('未找到运行包（payload/version.dll），请确认程序目录完整')
    prefix = runtime_prefix(runtime or DEFAULT_RUNTIME)
    for item in ENTRIES:
        fname, rel = item[1], item[2]
        if fname.lower() == entry_name.lower():
            p = src / (prefix + rel)
            if p.is_file():
                return p, ""
            return None, tr('运行包缺少 {0}').format(prefix + rel)
    return None, tr('未知入口 {0}').format(entry_name)


def verify_payload(runtime: str = "") -> list[str]:
    """校验运行包完整性。

    指定 runtime 时只校验该版本；未指定时校验全部版本，
    并允许某个版本整体缺失（返回缺包提示而非逐文件报错）。
    """
    warns: list[str] = []
    src = payload_dir()
    if not src:
        # 附带已查找位置，把哑报错变成可自查（纯诊断文本，不进 i18n 词典）
        tried = "；".join(str(p) for p in payload_search_paths())
        return [tr('未找到运行包目录，无法部署'),
                "已查找位置：" + tried]

    targets = [runtime] if runtime else [k for k, _p, _d in RUNTIMES]
    for rt in targets:
        prefix = runtime_prefix(rt)
        rels = [prefix + item[2] for item in ENTRIES]
        present = [r for r in rels if (src / r).is_file()]
        if not present:
            warns.append(tr('运行包缺少 {0} 整个版本目录').format(rt))
            continue
        for rel in rels:
            p = src / rel
            if not p.is_file():
                warns.append(tr('缺少文件 {0}').format(rel))
                continue
            want = PAYLOAD_SHA256.get(rel)
            if not want:
                continue
            try:
                got = sha256(p)
            except OSError as e:
                warns.append(tr('{0} 读取失败：{1}').format(rel, e))
                continue
            if got != want:
                warns.append(tr('{0} 哈希不符（本地 {1}… / 期望 {2}…）').format(
                    rel, got[:12], want[:12]))
    return warns


def _all_known_hashes() -> set[str]:
    """当前 payload 与历史版本的入口哈希合集（识别本项目部署）。

    含四部分：当前 0.3.2、上一版 0.3.1（PAYLOAD_SHA256_PREV）、
    再上一版 0.3.0（PAYLOAD_SHA256_030）、更早的 native 模式
    （PAYLOAD_SHA256_LEGACY）。升级部署时据此判定「这是本项目写入的
    文件」，可直接覆盖而不误判为第三方文件。
    """
    return (set(PAYLOAD_SHA256.values())
            | set(PAYLOAD_SHA256_PREV.values())
            | set(PAYLOAD_SHA256_030.values())
            | set(PAYLOAD_SHA256_LEGACY.values()))


def pick_entry(exe_dir: str, prefer: str = "") -> tuple[str, str]:
    """挑一个可用入口。

    顺序照上游 alternatives/README.md 的安全分层：
      工具类（version → winmm → dbghelp → dinput8）优先；
      渲染路径代理（dxgi / d3d12）不在自动选择内 —— 它们位于 D3D12 渲染热路径、
      加载顺序敏感，只有工具类都不行时才由用户在「高级」里手动指定。
    """
    order = [e[1] for e in ENTRIES if e[4] == "tool"]
    if prefer:
        order = [prefer] + [x for x in order if x != prefer]
    for fname in order:
        target = Path(exe_dir) / fname
        if not target.exists():
            return fname, ""
        try:
            if sha256(target) in _all_known_hashes():
                return fname, ""  # 本项目当前/历史部署，可直接覆盖
        except OSError:
            pass
    return "", tr('四种工具类入口名均已被其他程序占用；'
                  '可在「高级」里手动指定渲染路径代理（dxgi / d3d12，'
                  '二者只能选一个）')


def _entry_filename(name: str) -> str:
    """把入口名规范成 "xxx.dll" 形式。"""
    if not name:
        return ""
    n = str(name).strip().lower()
    return n if n.endswith(".dll") else f"{n}.dll"


def _is_running(exe_path: str) -> bool:
    if not exe_path:
        return False
    name = Path(exe_path).name
    out = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"])
    return name.lower() in out.lower()


def deploy(game: Game, router: str, mult: int, bilinear: bool, level: int,
           prefer_entry: str = "", force: bool = False,
           runtime: str = "", tier: int = DEFAULT_TIER) -> tuple[bool, list[str]]:
    """部署到游戏目录。

    runtime: 内嵌运行库版本（310.9 / 310.1），照搬上游两个发布包的结构；
             310.9 上限 6X，310.1 上限 4X。
    tier:    一致性档位 0–3（上游 0.3.2 的 Optimized）。310.1 上会被钳到 1。
    router/bilinear: 仅保留以兼容旧调用方，代理模式已无对应 ini 键。
    """
    logs: list[str] = []
    runtime = runtime or DEFAULT_RUNTIME
    if runtime not in [k for k, _p, _d in RUNTIMES]:
        return False, [tr('[错误] 未知运行库版本 {0}').format(runtime)]
    cap = runtime_mult_cap(runtime)
    if int(mult or 2) > cap:
        logs.append(tr('[提示] {0} 上限为 {1}X，已钳制。').format(
            runtime_label(runtime), cap))
        mult = cap

    tier, tier_clamp = clamp_tier(tier, runtime)
    if tier_clamp == "runtime_cap":
        logs.append(tr('[提示] 310.1 运行库没有有损图像内核，'
                       '档位 2/3 等同于档位 1，已按档位 1 写入。'))
    elif tier_clamp == "invalid":
        logs.append(tr('[提示] 档位值非法，已按上游行为回退到档位 1。'))
    exe_dir = Path(game.exe_dir)
    if not exe_dir.is_dir():
        return False, [tr('[错误] 目录不存在：{0}').format(exe_dir)]

    warns = verify_payload(runtime)
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

    src, err = payload_for_entry(entry, runtime)
    if not src:
        return False, logs + [tr('[错误] {0}').format(err)]

    if _is_running(game.exe):
        return False, logs + [tr('[错误] 游戏正在运行（{0}），请先完全退出再操作').format(Path(game.exe).name)]

    # 渲染路径代理互斥：dxgi 与 d3d12 只能留一个（上游 alternatives/README.md）
    if entry in RENDER_MUTEX:
        other = (RENDER_MUTEX - {entry}).pop()
        if (exe_dir / other).exists():
            return False, logs + [tr('[错误] {0} 与 {1} 不能同时存在；'
                                     '请先移除另一个再部署。').format(entry, other)]
        logs.append(tr('[警告] {0} 位于 D3D12 渲染热路径，加载顺序敏感，'
                       '仅在工具类代理都不可用时使用。').format(entry))

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
            if cur not in _all_known_hashes():
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

        ini_path.write_text(build_ini(router, mult, bilinear, level, tier, runtime),
                            encoding="utf-8")
        logs.append(f"[配置] {INI_NAME}：Optimized={tier}（{tr(tier_label(tier))}），"
                    f"MaxGeneratedFrames={max(1, min(5, int(mult) - 1))}"
                    f"（最高 {min(int(mult), cap)}X），"
                    f"Preset=Auto，运行库 {runtime}")
    except PermissionError as e:
        return False, logs + [tr('[错误] 权限不足或被占用：{0}').format(e),
                              tr('[提示] 以管理员身份运行本程序，并确认游戏已完全退出')]
    except Exception as e:
        return False, logs + [tr('[错误] 部署失败：{0}').format(e)]

    rec.update({
        "name": game.name, "exe_dir": str(exe_dir), "exe": game.exe, "entry": entry,
        "dll_sha256": sha256(target), "installed_at": time.time(),
        "runtime": runtime, "mult": mult, "level": level, "tier": tier,
        "source": game.source, "engine": game.engine, "dlssg": game.dlssg,
    })
    st["games"][key] = rec
    save_state(st)
    logs.append(tr('[完成] 已启用（{0}，档位 {1}）。重启游戏后进入画面设置，打开“帧生成”并选择倍率；'
                   '游戏支持动态插帧时最高可选 {2}X。').format(
                       runtime_label(runtime), tier, cap))
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
                if cur == rec.get("dll_sha256") or cur in _all_known_hashes():
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
    for k in ("Router", "KernelImage", "HardwareBilinear", "MaxGeneratedFrames", "Level",
              "Enabled", "Optimized", "OptimizedKernels", "Preset",
              "ImageApprox", "SkipRepeatedRealCopy"):
        m = re.search(rf"^{k}\s*=\s*(\S+)", txt, re.M)
        if m:
            cfg[k] = m.group(1)
    # 档位规范化：0.3.1 及更早只写 0/1，0.3.2 起写 0–3；
    # OptimizedKernels 是官方保留的向后兼容别名（两者都在时 Optimized 优先）。
    raw = cfg.get("Optimized") or cfg.get("OptimizedKernels")
    if raw is not None:
        try:
            t = int(raw)
            cfg["tier"] = t if TIER_MIN <= t <= TIER_MAX else DEFAULT_TIER
        except ValueError:
            cfg["tier"] = DEFAULT_TIER
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
        runtime = argv[argv.index("--runtime") + 1] if "--runtime" in argv else ""
        tier = int(argv[argv.index("--tier") + 1]) if "--tier" in argv else DEFAULT_TIER
        g = Game(name=Path(target).name, exe_dir=canon_dir(target))
        ok, logs = deploy(g, router, mult, "--bilinear" in argv, 1, entry, bool(entry),
                          runtime, tier)
        for l in logs:
            log(l)
        return 0 if ok else 1

    if "--restore" in argv:
        target = argv[argv.index("--restore") + 1]
        ok, logs = restore(Game(exe_dir=target))
        for l in logs:
            log(l)
        return 0 if ok else 1

    if "--update" in argv:
        info = check_update(include_upstream="--no-upstream" not in argv)
        print(json.dumps(asdict(info), ensure_ascii=False, indent=2))
        return 0 if info.ok else 1

    print(f"{APP_NAME} {APP_VERSION}")
    print("  --gpu                 显示显卡探测结果")
    print("  --update              检查是否有新版本（--no-upstream 跳过上游检查）")
    print("  --hags [--on|--off]   查看 / 开启 / 关闭硬件加速 GPU 计划")
    print("  --scan [--deep <盘符>] 扫描游戏并输出 JSON")
    print("  --install <EXE目录> [--router SM86|SM75] [--mult 2|3|4] [--bilinear]"
          " [--entry <入口>] [--runtime 310.9|310.1] [--tier 0|1|2|3]")
    print("  --restore <EXE目录>")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
