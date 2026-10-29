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
import tempfile
import time
import urllib.error
import zipfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import winreg
except ImportError:  # 非 Windows 平台的占位，实际逻辑不会走到
    winreg = None  # type: ignore

import i18n
from i18n import tr  # 多语言：中文字面量为源键，详见 i18n.py
from upstream_payload import (
    PAYLOAD_FILES_SHA256,
    UPSTREAM_ARCHIVE_SHA256,
    UPSTREAM_VERSION,
)

APP_NAME = "DLSSG Manager"
APP_VERSION = "1.9.6"
APP_TITLE = f"{APP_NAME} {APP_VERSION}"

# 界面缩放：由用户在标题栏选择，持久化到 state.json，启动时通过
# QT_SCALE_FACTOR 整体缩放（含字体、间距与图标），避免只放大字号导致错位。
UI_SCALES = (1.0, 1.1, 1.25, 1.5)
UI_SCALE_DEFAULT = 1.0
UI_SCALE_MIN = 0.8
UI_SCALE_MAX = 2.0

# 内嵌的上游 Mod 版本 —— 全项目只在这里声明一次。
# MOD_NAME 供界面/日志显示，PAYLOAD_SHA256 由它索引到对应版本的哈希表。
MOD_VERSION = UPSTREAM_VERSION
MOD_NAME = f"DLSSG SM86 {MOD_VERSION}"

INI_NAME = "dlssg_sm86.ini"
LOG_DIR_NAME = "dlssg_sm86"

# 上游 0.4.x 采用一个独立运行包目录，310.9.16 随包放在 dlssg_sm86/runtime。
# 0.3.5 是 0.4.x 之前的最后一个稳定版：代理 DLL 自带运行库，不需要
# dlssg_sm86/ 目录。它仍被保留为兼容回退项 —— 0.4.x 在部分游戏上会
# 因新运行库 / 驱动拒绝而无法进入，而 0.3.5 在这些游戏上仍可注入。
RUNTIMES = [
    ("310.9.16", "", "310.9.16 运行库（上游 0.4.1）"),
    ("310.9", "", "310.9 运行库（上游 0.3.5 兼容）"),
    ("310.1", "310.1/", "310.1 运行库（上游 0.3.5 兼容）"),
]
DEFAULT_RUNTIME = "310.9.16"

# 兼容回退包：0.3.5 的 12 个代理（310.9 / 310.1 各 6 个入口）压成一个
# 压缩包，首次选用时解到 %LOCALAPPDATA%\DLSSGManager\packs\ 下。这样
# 安装包不用常驻 360 MB 的旧 DLL，只有需要回退的用户才展开它。
LEGACY_UPSTREAM_VERSION = "0.3.5"
LEGACY_RUNTIMES = ("310.9", "310.1")
LEGACY_PACK_ARCHIVE = "packs/upstream-0.3.5-x64.zip"
LEGACY_PACK_DIRNAME = "upstream-0.3.5"

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

# 当前内嵌与历史版本的入口哈希，按上游版本号索引（识别本项目部署）。
# 键为「包内相对路径去掉运行库前缀」。
# 同步上游时只需两步：在下面加一条新版本、把 MOD_VERSION 改成它。
#   · 当前 0.3.5 —— 修复自 0.3.0 起「游戏重建帧生成特性后用错优化内核」的缺陷
#     （花屏 / 随机崩溃 / 驱动重置，#561；Optimized=0 不受影响）。
#   · 0.3.4 —— 修复 0.3.3 在 RTX 30 上的驱动重置崩溃。
#   · 0.3.2 —— 重写 310.9 的 26 个推理内核；档位由 0/1 改为 0–3 四级。
#   · 0.3.1 —— 恢复 RTX 20（SM75）支持、INI 逐键回退、出厂 4X。
#   · 0.3.0 —— 代理模式首版。
# 保留全部历史版本，是为了让旧部署能被认出来、直接覆盖升级，
# 而不是被误判成第三方文件。
PAYLOAD_SHA256_BY_VERSION: dict[str, dict[str, str]] = {
    "0.3.5": {
        # --- 310.9（根目录，上游 0.3.5）---
        "version.dll": "c3934a09399f022504227c72df0bf8c0de55f9a08880dddde898c5262cefa838",

        # --- 310.1（310.1/ 子目录，上游 0.3.5）---
        "alternatives/winmm.dll": "bc3cef25c1ccbbdccdd93db9fae845104bb6c71fd433240e26641881a7e46658",
        "alternatives/dbghelp.dll": "dfe7f44baa68d237dfe040d4b4cfc9bd44b01e661f3051996db1144e6bb388cb",
        "alternatives/dinput8.dll": "4fbad08bb9360a1cd1309a82586353484fe64b7220199344ab83fae308176c6b",
        "alternatives/dxgi.dll": "52e67020a725c74d5dee62aee4dc166a2f4e5c3adabf04ecab3005ab968fc24d",
        "alternatives/d3d12.dll": "64b7ecc3f6d70011feed8dfaa20ce500522e8b04170142e2a2000146b4d7ac71",
        "310.1/version.dll": "4ba7fecc68e2229193757839f326176a4f0f4325baab3c324007e0ea844e4d17",
        "310.1/alternatives/winmm.dll": "a62e669d2ceae7645cbafe98d1df69892ede07bf78166acf2185a8beb9843a85",
        "310.1/alternatives/dbghelp.dll": "fc58ee19b315732821ea3216d4d360972c38ce076ebc7d730b3f601c0e5c4a2c",
        "310.1/alternatives/dinput8.dll": "ed56447cefa8b5836ec39116db620c289cac783fba938a9740c7a1b845a6ffaa",
        "310.1/alternatives/dxgi.dll": "682e9a1318c5e2cb4ccf490c6cabfa2f119bf2f4793ced9c68ea56f3a21dc288",
        "310.1/alternatives/d3d12.dll": "1b6c39e4e2aa34e216d70d991ecb3d83eb6bdc01fa5e977a2e837f4433f77f2b",
    },

    "0.3.4": {
        # --- 310.9（根目录，上游 0.3.4）---
        "version.dll": "575c9bb475c836cef3c40d7195656955e14220aa9f0f7dde9d817a91911cb85f",

        # --- 310.1（310.1/ 子目录，上游 0.3.4）---
        "alternatives/winmm.dll": "84bfa1c4a68711439a92400cce5f80ce0ba3378caefb17b85e388a0fb60bc53c",
        "alternatives/dbghelp.dll": "50e1c50cb45a5512bcead3ea22da560776db67f7ab8f7fe9c583b4ecee7b7a41",
        "alternatives/dinput8.dll": "ccc0fc43f9ac1a622f37c71ea480dd75641cb6426af8023ed344a89189af5c8c",
        "alternatives/dxgi.dll": "af12e17d4fc22d94fa84f7fe9f306c43ebfd9dcb7cbeb41d01a018138586a922",
        "alternatives/d3d12.dll": "517f70f46d6b2354514fb5461c53c0db9b9ef0dae46d16c05b92d2fc843514db",
        "310.1/version.dll": "a4d04765f9e679aa91bfc9784253b7bd8d0ada828de7ed36e322ce714988de47",
        "310.1/alternatives/winmm.dll": "8738dd6028db37a8269bbc7b71a1616abd352bb46c60de805b201883dad0d05e",
        "310.1/alternatives/dbghelp.dll": "29e7ede3d1d6a27dff0795d5fb084874052f8df79534a722ad97e98da6dc36d8",
        "310.1/alternatives/dinput8.dll": "7f18c06d48f9a0836eac23105627aaa1b799ae0bd7a45c4d84c87032e5e994eb",
        "310.1/alternatives/dxgi.dll": "44754245d1e27675004fcd1a6b297b999377c65db0004c31bc617edb7a7aa5dd",
        "310.1/alternatives/d3d12.dll": "081b0fe43db0e8f2caa1c3457538f972859e9e5fca61461363d4f78d28861d26",
    },

    "0.3.2": {
        # --- 310.9（根目录，上游 0.3.2）---
        "version.dll": "39b16f2cdb16450f0edc0e0b14231951e10954131ad9aa12037700e18dc91040",

        # --- 310.1（310.1/ 子目录，上游 0.3.2）---
        "alternatives/winmm.dll": "f36ced34bbcd28c09f70c0d6adad2e1f9b1659cda46a204cc01a38d1ae86da37",
        "alternatives/dbghelp.dll": "67e04932c9e1d980d6431ec626f4db21b78a1375e95de6e7e9366f58f0cb9a65",
        "alternatives/dinput8.dll": "6fe34c8c291fb5be21184076b14b52b6e01de88a263ae0d10f6daa68e0bb5d4e",
        "alternatives/dxgi.dll": "988f1da4397779fd901924d793dba967d0ffa44bfaa8f9ab25b5c5641ab93ffc",
        "alternatives/d3d12.dll": "5b36c5d068b64f7413d75d30fcfa35539da26bd75452bab2a1340baf26da0fe8",
        "310.1/version.dll": "a1f5e4c8c43238de5b639ef858fb67fbb1874e5e8681833bc3ffff4d3b573c50",
        "310.1/alternatives/winmm.dll": "f20bff1fa5f9a9dc6b7a35ce16fc8c743a7a34a1a47c116283b682f2260b6107",
        "310.1/alternatives/dbghelp.dll": "d17643ae2aed871a646f92ff6613e0604dedab2dc4ec8c8f7f2294f1ec9f7013",
        "310.1/alternatives/dinput8.dll": "1893acb44f84185a21a5a92b6349a2227e39cefb6a901bae1025174b5c60261a",
        "310.1/alternatives/dxgi.dll": "ecc28978ff578489ea88fbd9f1c18b566f8b5d5574003e947dfbfa66e177544c",
        "310.1/alternatives/d3d12.dll": "05a83f28c942148e75d11897cc9ea9f1f3a90613a3e0aac2eea0118a016fcc54",
    },

    "0.3.1": {
        # --- 310.9（根目录，上游 0.3.1）---
        "version.dll": "3d4c7d537a6e71e3a9d41ffc6487e054b26c56d27b7c0825d39eaa7ef0c7e86d",

        # --- 310.1（310.1/ 子目录，上游 0.3.1）---
        "alternatives/winmm.dll": "40eaa7dff6eb6281917eb84aa1c6e580c9e69f8736b647d28decb561f6efd7eb",
        "alternatives/dbghelp.dll": "13071d2a8cccd5a4707eedd5ccf00aee6df8b6aceba03e7c1dda9358f0f2c998",
        "alternatives/dinput8.dll": "9f77a9070a7a3277f3d7e405e49e61de7e53101e2925f75bacd9cc204e14a0da",
        "alternatives/dxgi.dll": "539138464137855f5962811588000a95897b3ddb14f5b44a197e37c3e17bd9fb",
        "alternatives/d3d12.dll": "30b48198f0cd100827037bdbe27b2a15bc050ff1c276c520ffc41705920f07b1",
        "310.1/version.dll": "ca4146f76d4b176d17246d8c0e66042c57f7b25dcabea3200b33821522597211",
        "310.1/alternatives/winmm.dll": "2312e761ee589204ddf4d402c1ae36367aa73d9bcd9fdfd9bbe56c06604a63e6",
        "310.1/alternatives/dbghelp.dll": "c4679d28f69e5c99aec290725ef930a2fc58c657514f65f650efdbb0a308143c",
        "310.1/alternatives/dinput8.dll": "94767cc139f8ecb6373765cd102cc85a28601cd55101f53ae854e61a4cbf4868",
        "310.1/alternatives/dxgi.dll": "7dec971ff126f427b855d1238ff2b2ecb6ab7616c467776f882e7a4e244cc5b5",
        "310.1/alternatives/d3d12.dll": "77860075059a630a90327e417cae7db6067ff56878ddb429d5d741c813dd4995",
    },

    "0.3.0": {
        # --- 310.9（根目录，上游 0.3.0）---
        "version.dll": "a22d2453f25d7df3fdc0d6d683c21f01769a115439d58f1341183a75faaf8c7d",

        # --- 310.1（310.1/ 子目录，上游 0.3.0）---
        "alternatives/winmm.dll": "197f97e90541ae688d291ef388b1eddc0c55cb657603eb55dea2d3d178b1e384",
        "alternatives/dbghelp.dll": "10e2fe2d84b8b674e184891ca5211b01c43c6700e1c8b8c6d4969286f653bff8",
        "alternatives/dinput8.dll": "01fdd5e77e64045400a2e7b6f35f98f3403335e30cd9def0e996f78240aa65da",
        "alternatives/dxgi.dll": "ae37150fe056f3388571481ad4aaf78fad720e9b52eb7e6e1e9d2dff85df841e",
        "alternatives/d3d12.dll": "63e7c3a1ba0b10e37e1a162ccf3aa2e19a0f7359de63787585c09baffd67ad45",
        "310.1/version.dll": "4646fe15a21c01d251865253f55cefd5892dd2e561ece0c8efa49ae78b5de32e",
        "310.1/alternatives/winmm.dll": "dde7ec668130b09f807338c4c594609a75349860bb5ca4428797f6ab2175b9c1",
        "310.1/alternatives/dbghelp.dll": "1537a207f6490f49373ac8164e2021e6f25bd212e4abc8564dfd8110ad3afe28",
        "310.1/alternatives/dinput8.dll": "e87a61ef84f60b58e5f3b841006992a30d8fd2998096f065b317e7126ebccd9b",
        "310.1/alternatives/dxgi.dll": "f8d823609f994861d27abf50c9cb78386202650f8da1c868eaa2a40f13feef70",
        "310.1/alternatives/d3d12.dll": "337ed97b9303192915e6edcac0310dca8817f72baa414dffa83d238cdb2ca724",
    },
}

# 保留原名给现有调用方（verify_payload / 校验脚本）用。
PAYLOAD_SHA256_BY_VERSION[UPSTREAM_VERSION] = dict(PAYLOAD_FILES_SHA256)
PAYLOAD_SHA256 = PAYLOAD_SHA256_BY_VERSION[MOD_VERSION]



def runtime_prefix(rt: str) -> str:
    """0.4.1 的运行库随 dlssg_sm86/ 一起部署；0.3.5 的 310.1 在 310.1/ 子目录。"""
    for key, prefix, _desc in RUNTIMES:
        if key == rt:
            return prefix
    return ""


def runtime_is_legacy(rt: str) -> bool:
    """该运行库是否来自 0.3.5 兼容包（单文件代理，无 dlssg_sm86/ 目录）。"""
    return (rt or DEFAULT_RUNTIME) in LEGACY_RUNTIMES


def runtime_upstream(rt: str) -> str:
    """运行库对应的上游版本号。"""
    return LEGACY_UPSTREAM_VERSION if runtime_is_legacy(rt) else UPSTREAM_VERSION


def runtime_mult_cap(rt: str = DEFAULT_RUNTIME, engine: str = "DLSS") -> int:
    """上游 DLSS 最高 6X，XeSS-FG 最高 4X；0.3.5 的 310.1 最高 4X。"""
    if engine.upper() == "XESS":
        return 4
    if (rt or DEFAULT_RUNTIME) == "310.1":
        return 4
    return 6


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
    """0.4.1 支持四档；0.3.5 的 310.9 支持四档，310.1 只有档位 0/1。"""
    return 1 if (runtime or DEFAULT_RUNTIME) == "310.1" else TIER_MAX


def tier_label(tier: int) -> str:
    """档位的用户可读名（同时用作 i18n 键）。"""
    return {
        0: '0 原厂（最保守）',
        1: '1 逐位一致（推荐）',
        2: '2 更快（有损）',
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


# ---------------------------------------------------------------- 0.3.5 兼容包

def legacy_pack_archive() -> Path | None:
    """定位随包的 0.3.5 兼容压缩包（payload/packs/...）。"""
    for cand in payload_search_paths():
        p = cand / LEGACY_PACK_ARCHIVE
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def legacy_pack_root() -> Path:
    return data_dir() / "packs" / LEGACY_PACK_DIRNAME


def legacy_pack_ready(root: Path | None = None) -> bool:
    """兼容包是否已解压且逐文件哈希一致。"""
    root = root or legacy_pack_root()
    table = PAYLOAD_SHA256_BY_VERSION.get(LEGACY_UPSTREAM_VERSION) or {}
    if not table:
        return False
    for rel, want in table.items():
        p = root / rel
        try:
            if not p.is_file() or sha256(p) != want:
                return False
        except OSError:
            return False
    return True


def _safe_zip_member(name: str) -> tuple[str, ...] | None:
    """校验压缩包成员路径，拒绝绝对路径、盘符、.. 和反斜杠。"""
    if "\\" in name or any(ord(ch) < 32 for ch in name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    parts = tuple(part for part in name.split("/") if part not in ("", "."))
    if name.startswith("/") or ".." in parts or not parts:
        raise ValueError(f"Unsafe archive path: {name!r}")
    if len(parts[0]) == 2 and parts[0][1] == ":":
        raise ValueError(f"Unsafe archive path: {name!r}")
    return parts


def ensure_legacy_pack() -> tuple[Path | None, str]:
    """解压并校验 0.3.5 兼容包；返回 (目录, 错误)。"""
    root = legacy_pack_root()
    if legacy_pack_ready(root):
        return root, ""
    archive = legacy_pack_archive()
    if not archive:
        return None, tr('未找到旧版兼容包 {0}，请确认程序目录完整').format(LEGACY_PACK_ARCHIVE)
    table = PAYLOAD_SHA256_BY_VERSION.get(LEGACY_UPSTREAM_VERSION) or {}
    if not table:
        return None, tr('程序内置的旧版文件清单缺失')
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pack-0.3.5-", dir=root.parent))
    try:
        with zipfile.ZipFile(archive) as zf:
            if zf.testzip() is not None:
                raise ValueError("兼容包校验失败（CRC）")
            seen: set[str] = set()
            for info in zf.infolist():
                if info.is_dir():
                    continue
                parts = _safe_zip_member(info.filename)
                if parts is None:
                    continue
                key = "/".join(parts).casefold()
                if key in seen:
                    raise ValueError(f"兼容包内重复路径：{info.filename}")
                seen.add(key)
                target = stage.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                if target.stat().st_size != info.file_size:
                    raise ValueError(f"兼容包解压长度不符：{info.filename}")
        for rel, want in table.items():
            p = stage / rel
            if not p.is_file():
                raise ValueError(f"兼容包缺少文件：{rel}")
            if sha256(p) != want:
                raise ValueError(f"兼容包文件哈希不符：{rel}")
        if root.exists():
            shutil.rmtree(root)
        os.replace(stage, root)
        return root, ""
    except Exception as e:
        shutil.rmtree(stage, ignore_errors=True)
        return None, tr('旧版兼容包无法使用：{0}').format(e)


def pack_dir(runtime: str = "") -> tuple[Path | None, str]:
    """运行包根目录：0.4.x 用 payload/，0.3.5 用解压后的兼容包。"""
    rt = runtime or DEFAULT_RUNTIME
    if runtime_is_legacy(rt):
        return ensure_legacy_pack()
    src = payload_dir()
    if not src:
        return None, tr('未找到运行包（payload/version.dll），请确认程序目录完整')
    return src, ""


def support_files_for(runtime: str = "") -> tuple[str, ...]:
    """该运行库需要随代理一起部署的附属文件（0.3.5 全部内嵌在代理里）。"""
    return () if runtime_is_legacy(runtime) else GAME_SUPPORT_FILES


def prune_empty_dirs(root: Path) -> None:
    """删除空目录树（只删空目录，日志和用户文件不受影响）。"""
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass
    try:
        root.rmdir()
    except OSError:
        pass



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


# ---------------------------------------------------------------- 显卡设备重启
# cfgmgr32.h 的设备节点状态位
DN_NEED_RESTART = 0x00000100


def _devnode_status(instance_id: str) -> tuple[int, int] | None:
    """读取设备节点状态位，返回 (status, problem)；查不到返回 None。

    只读查询，不改动设备。用于判断系统是否已把该设备标记为「等待重启」。
    """
    if os.name != "nt" or not instance_id:
        return None
    try:
        import ctypes

        cfg = ctypes.WinDLL("cfgmgr32")
        cfg.CM_Locate_DevNodeW.argtypes = (ctypes.POINTER(ctypes.c_uint32),
                                           ctypes.c_wchar_p, ctypes.c_ulong)
        cfg.CM_Locate_DevNodeW.restype = ctypes.c_ulong
        cfg.CM_Get_DevNode_Status.argtypes = (ctypes.POINTER(ctypes.c_uint32),
                                              ctypes.POINTER(ctypes.c_uint32),
                                              ctypes.c_uint32, ctypes.c_ulong)
        cfg.CM_Get_DevNode_Status.restype = ctypes.c_ulong
        devinst = ctypes.c_uint32(0)
        if cfg.CM_Locate_DevNodeW(ctypes.byref(devinst), instance_id, 0) != 0:
            return None
        status = ctypes.c_uint32(0)
        problem = ctypes.c_uint32(0)
        if cfg.CM_Get_DevNode_Status(ctypes.byref(status), ctypes.byref(problem),
                                     devinst, 0) != 0:
            return None
        return int(status.value), int(problem.value)
    except Exception:
        return None


def gpu_device_needs_reboot() -> bool:
    """显卡设备是否已被系统标记为「等待重启」（DN_NEED_RESTART）。

    处在该状态时 pnputil /restart-device 会返回 ERROR_NOT_SUPPORTED(50)，
    驱动栈拒绝就地重启，只能重启电脑完成配置。
    """
    info = detect_gpu_mask()
    if not info.enum_key:
        return False
    status = _devnode_status(info.enum_key.split("Enum\\", 1)[-1])
    return bool(status and (status[0] & DN_NEED_RESTART))


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _restart_via_pnputil(instance_id: str) -> tuple[bool, str, bool]:
    """pnputil /restart-device。返回 (成功, 输出, 该命令是否不被支持)。"""
    try:
        r = subprocess.run(["pnputil", "/restart-device", instance_id],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60,
                           creationflags=_no_window_flag())
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", False
    out = ((r.stderr or "") + " " + (r.stdout or "")).strip()
    low = out.lower()
    unsupported = (r.returncode == 50 or "not supported" in low
                   or "不支持" in out)
    return r.returncode == 0, out, unsupported


def _restart_via_powershell(instance_id: str) -> tuple[bool, str]:
    """备用路径：Disable-PnpDevice + Enable-PnpDevice（等价于设备管理器禁用/启用）。"""
    inst = instance_id.replace("'", "''")
    ps = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "$ErrorActionPreference='Stop';"
        f"$id='{inst}';"
        "Disable-PnpDevice -InstanceId $id -Confirm:$false;"
        "Start-Sleep -Milliseconds 800;"
        "Enable-PnpDevice -InstanceId $id -Confirm:$false;"
        "'OK'"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-Command", ps],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120,
                           creationflags=_no_window_flag())
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    out = ((r.stderr or "") + " " + (r.stdout or "")).strip()
    if r.returncode == 0 and "OK" in (r.stdout or ""):
        return True, ""
    return False, out[-300:] or f"code={r.returncode}"


def restart_gpu_device() -> tuple[bool, str]:
    """重启显卡设备，让名称改动立即生效。

    DXGI 在驱动初始化时缓存适配器名称，改注册表后不重启不会刷新
    （实测：改完立即读 DXGI 仍是旧名，重启设备后变为新名）。
    先查设备节点是否已被标记「等待重启」：这种状态下 pnputil 一律失败，
    只能重启电脑；否则 pnputil 优先，不被支持时退回设备管理器式禁用/启用。
    """
    if os.name != "nt":
        return False, tr('非 Windows 系统')
    if not is_admin():
        return False, tr('需要管理员权限才能重启显卡设备')
    info = detect_gpu_mask(force=True)
    if not info.enum_key:
        return False, tr('未找到 NVIDIA 显卡设备实例')
    inst = info.enum_key.split("Enum\\", 1)[-1]

    if gpu_device_needs_reboot():
        return False, tr('显卡设备已被系统标记为「等待重启」，重启设备无法完成配置，需要重启电脑后生效。')

    ok, out, unsupported = _restart_via_pnputil(inst)
    if ok:
        return True, tr('已重启显卡设备，新的显卡名称立即生效')
    if not unsupported:
        return False, tr('重启设备失败：{0}').format(out[:200] or '未知原因')

    ok2, detail2 = _restart_via_powershell(inst)
    if ok2:
        return True, tr('已重启显卡设备，新的显卡名称立即生效')
    return False, tr('重启设备失败：{0}').format(detail2[:200] or '未知原因')


def schedule_reboot(delay_seconds: int = 60) -> tuple[bool, str]:
    """安排重启电脑（delay 秒后），用于让显卡名称配置生效。"""
    if os.name != "nt":
        return False, tr('非 Windows 系统')
    if not is_admin():
        return False, tr('需要管理员权限才能安排重启')
    delay = max(0, min(int(delay_seconds), 86400))
    try:
        r = subprocess.run(["shutdown", "/r", "/t", str(delay)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20,
                           creationflags=_no_window_flag())
    except Exception as e:
        return False, tr('重启计划失败：{0}: {1}').format(type(e).__name__, e)
    if r.returncode == 0:
        return True, tr('已安排在 {0} 秒后重启电脑').format(delay)
    detail = ((r.stderr or r.stdout or '').strip() or f"code={r.returncode}")[:200]
    return False, tr('重启计划失败：{0}').format(detail)


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
REPO_PAGE = f"https://github.com/{UPDATE_REPO}"
UPDATE_TIMEOUT = 8          # 秒；超时即视为检查失败，不阻塞界面
UPDATE_CACHE_HOURS = 6      # 同一版本内的静默检查间隔（小时）


@dataclass
class UpdateInfo:
    """一次更新检查的结果。"""

    ok: bool = False                 # 是否成功完成检查（网络/解析都正常）
    version: str = ""                # 远端最新版本号（已去掉前导 v）
    is_newer: bool = False           # 远端版本是否高于本机
    url: str = UPDATE_PAGE           # 下载页
    notes: str = ""                  # Release 说明（可能为空）
    published: str = ""              # 发布时间（ISO 字符串，可能为空）
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


def check_update() -> UpdateInfo:
    """检查本工具是否有新版本。

    只做一次只读 GET，不上传任何数据。任何失败都返回 ok=False + error，
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
    t0 = time.monotonic()
    next_progress = t0 + 0.4
    base = len(rp.parts)
    hits: list[str] = []
    try:
        for cur, dirs, files in os.walk(rp):
            now = time.monotonic()
            if now - t0 > budget_sec:
                break
            depth = len(Path(cur).parts) - base
            if depth >= 7:
                dirs[:] = []
            dirs[:] = [d for d in dirs
                       if d.lower() not in DIR_BLACKLIST and d.lower() not in SKIP_ROOTS]
            if progress and now >= next_progress:
                progress(tr('深度扫描中… {0}s').format(int(now - t0)))
                next_progress = now + 0.4
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
            st["settings"].setdefault("ui_scale", UI_SCALE_DEFAULT)
            if not isinstance(st.get("ignored_games"), list):
                st["ignored_games"] = []
            return st
        except Exception:
            pass
    return {"games": {}, "roots": [], "ignored_games": [],
            "settings": {"mult": 4, "bilinear": False, "level": 1,
                         "auto_update_check": True, "ui_scale": UI_SCALE_DEFAULT}}


def saved_ui_scale(state: dict | None = None) -> float:
    """Read the persisted UI scale, clamped to a sane range.

    The value is applied at process start through QT_SCALE_FACTOR, so the whole
    interface (fonts, paddings, icons) scales consistently on any DPI.
    """
    st = state if state is not None else load_state()
    try:
        value = float((st.get("settings") or {}).get("ui_scale", UI_SCALE_DEFAULT))
    except (TypeError, ValueError):
        return UI_SCALE_DEFAULT
    if not (UI_SCALE_MIN <= value <= UI_SCALE_MAX):
        return UI_SCALE_DEFAULT
    return round(value, 3)


def save_state(state: dict) -> None:
    tmp = state_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_file())


def ignored_game_records(state: dict) -> list[dict]:
    """Return normalized ignored-game records without mutating user state."""
    records = state.get("ignored_games", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)
            and (record.get("gid") or record.get("exe_dir") or record.get("install_dir"))]


def ignore_game(state: dict, game: Game) -> dict:
    """Hide a scanned game from future results; never removes game files."""
    record = {
        "gid": str(game.gid or game_key(game.exe_dir)),
        "name": str(game.name or game.install_dir or "Game"),
        "source": str(game.source or ""),
        "install_dir": canon_dir(game.install_dir),
        "exe_dir": canon_dir(game.exe_dir),
    }
    records = ignored_game_records(state)
    records = [old for old in records
               if old.get("gid") != record["gid"]
               and norm(canon_dir(old.get("exe_dir", ""))) != norm(record["exe_dir"])]
    records.append(record)
    state["ignored_games"] = records
    return record


def unignore_game(state: dict, gid: str) -> dict | None:
    """Remove one ignored-game rule and return its record, if found."""
    records = ignored_game_records(state)
    record = next((r for r in records if str(r.get("gid", "")) == str(gid)), None)
    if record is not None:
        state["ignored_games"] = [r for r in records if r is not record]
    return record


def _ignored_game_indexes(state: dict) -> tuple[set[str], set[str], set[str]]:
    gids: set[str] = set()
    install_dirs: set[str] = set()
    exe_dirs: set[str] = set()
    for record in ignored_game_records(state):
        if record.get("gid"):
            gids.add(str(record["gid"]))
        for field, target in (("install_dir", install_dirs), ("exe_dir", exe_dirs)):
            path = str(record.get(field, "") or "")
            if path:
                target.add(norm(canon_dir(path)))
    return gids, install_dirs, exe_dirs


def is_game_ignored(game: Game, state: dict) -> bool:
    gids, install_dirs, exe_dirs = _ignored_game_indexes(state)
    return (str(game.gid) in gids
            or norm(canon_dir(game.install_dir)) in install_dirs
            or norm(canon_dir(game.exe_dir)) in exe_dirs)


def filter_ignored_games(games: list[Game], state: dict) -> list[Game]:
    return [game for game in games if not is_game_ignored(game, state)]


def game_key(exe_dir: str) -> str:
    return hashlib.sha1(norm(exe_dir).encode("utf-8")).hexdigest()[:16]


def entry_of_deployment(exe_dir: str) -> tuple[str, bool]:
    """检查目录里是否已有本项目的部署。返回 (入口文件名, 是否确认属于本项目)。"""
    d = Path(exe_dir)
    ini = d / INI_NAME
    has_our_ini = False
    try:
        if ini.is_file():
            head = read_text(ini)[:4096]
            has_our_ini = APP_NAME in head and ("生成" in head or "Generated by" in head)
    except OSError:
        pass
    known = _all_known_hashes()

    # Multiple known proxies can survive older deploys. Prefer the entry this
    # game record says we installed, rather than the first matching filename.
    try:
        record = (load_state().get("games") or {}).get(game_key(str(d)), {})
    except Exception:
        record = {}
    preferred = str(record.get("entry") or "").strip().lower()
    if preferred in {item[1] for item in ENTRIES}:
        f = d / preferred
        try:
            digest = sha256(f) if f.is_file() and not f.is_symlink() else ""
            if (digest in known
                    or record.get("dll_sha256") == digest
                    or (record.get("managed_files") or {}).get(preferred) == digest):
                return preferred, True
        except OSError:
            pass

    for item in ENTRIES:
        fname = item[1]
        f = d / fname
        if f.is_file():
            try:
                if sha256(f) in known:
                    return fname, True
            except OSError:
                pass
    return ("", has_our_ini)


# ---------------------------------------------------------------- 部署 / 恢复

def _set_ini_value(text: str, section: str, key: str, value: str) -> str:
    """在官方模板的指定节里替换一个键；模板不匹配时拒绝部署。"""
    lines = text.splitlines(keepends=True)
    current = ""
    key_pattern = re.compile(rf"^([ \t]*{re.escape(key)}[ \t]*=[ \t]*)[^\r\n]*")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            continue
        if current != section or stripped.startswith((";", "#")):
            continue
        match = key_pattern.match(line)
        if match:
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            lines[i] = match.group(1) + value + newline
            return "".join(lines)
    raise ValueError(f"Upstream INI template is missing [{section}] {key}")


def _merge_compatible_ini(template: str, previous: str) -> str:
    """Carry forward advanced values only when the new upstream template still supports them."""
    section = ""
    for line in previous.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        if not stripped or stripped.startswith((";", "#")) or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key, value = key.strip(), value.strip()
        if section and key and value:
            try:
                template = _set_ini_value(template, section, key, value)
            except ValueError:
                # Removed/renamed upstream options are deliberately dropped.
                continue
    return template


def _build_legacy_ini(mult: int, level: int, tier: int, runtime: str) -> str:
    """按上游 0.3.5 的键位生成旧格式配置。

    0.3.5 的代理把运行库内嵌在 DLL 里，不吃 0.4.x 的 [DLSSG] / [SuperResolution]
    等键，只认 [FrameGeneration] Optimized 与 [Compatibility] Preset。写错键位
    不会报错，只会静默按默认值运行，所以这里必须逐字对齐旧版格式。
    """
    cap = runtime_mult_cap(runtime, "DLSS")
    mult = max(2, min(cap, int(mult or 2)))
    tier, _reason = clamp_tier(tier, runtime)
    level = max(0, min(3, int(level)))
    lines = [
        f"; DLSSG SM86 {LEGACY_UPSTREAM_VERSION} · {APP_NAME} {APP_VERSION}",
        "; Generated by DLSSG Manager（由本工具生成）；修改后需重启游戏才生效。",
        "; 本文件只覆盖下面列出的键，其余保持上游默认。",
        "",
        "[General]",
        "; 1 = 启用插帧；0 = 关闭，游戏自带的 DLSS-G 保持原样。",
        "Enabled=1",
        "",
        "[FrameGeneration]",
        "; 一致性档位：0 = 原厂内核；1 = 逐位一致（推荐）；2 / 3 = 有损加速。",
        "; 310.1 只支持 0 / 1（档位 2 / 3 在该运行库上等同档位 1）。",
        f"Optimized={tier}",
        "; 额外生成帧数：5 = 最高 6X（310.9）；3 = 最高 4X（310.1）。",
        f"MaxGeneratedFrames={mult - 1}",
        "",
        "[Compatibility]",
        "; 0.3.5 只有 Auto：由游戏/运行库自行决定，不提供 0.4.x 的 A/B/C 预设。",
        "Preset=Auto",
        "",
        "[Logging]",
        f"Level={level}",
        "Directory=dlssg_sm86\\logs",
        "",
        "[Runtime]",
        "; Bundled = 始终使用代理内嵌的运行库，不会读取 dlssg_sm86/ 目录。",
        "Mode=Bundled",
        "CacheDirectory=",
        "",
    ]
    return "\r\n".join(lines)


def build_ini(router: str, mult: int, bilinear: bool, level: int,
              tier: int = DEFAULT_TIER, runtime: str = "",
              engine: str = "DLSS", preset: str = "A",
              sr_mode: str = "Off", previous: str = "") -> str:
    """生成运行库配置：0.4.x 用上游完整模板，0.3.5 用旧格式模板。"""
    rt = runtime or DEFAULT_RUNTIME
    if runtime_is_legacy(rt):
        return _build_legacy_ini(mult, level, tier, rt)

    source = payload_dir()
    template_path = source / INI_NAME if source else None
    if not template_path or not template_path.is_file():
        raise FileNotFoundError("缺少经过校验的上游 dlssg_sm86.ini 模板")
    engine_key = engine.strip().upper()
    if engine_key not in {"DLSS", "XESS"}:
        raise ValueError(f"Unsupported frame-generation engine: {engine}")
    engine = "XeSS" if engine_key == "XESS" else "DLSS"
    preset = preset.upper()
    if preset not in {"A", "B", "C"}:
        raise ValueError(f"Unsupported DLSS-G preset: {preset}")
    if sr_mode not in {"Off", "M-INT8", "L-INT8", "M-FP16", "L-FP16"}:
        raise ValueError(f"Unsupported super-resolution mode: {sr_mode}")
    cap = runtime_mult_cap(runtime or DEFAULT_RUNTIME, engine)
    mult = max(2, min(cap, int(mult or 2)))
    tier, _reason = clamp_tier(tier, runtime or DEFAULT_RUNTIME)

    text = read_text(template_path)
    if previous:
        text = _merge_compatible_ini(text, previous)
    text = text.replace("DLSSG SM86 - frame generation", f"DLSSG SM86 {MOD_VERSION} - frame generation", 1)
    text = text.replace("; Copy version.dll",
                        f"; Generated by {APP_NAME} {APP_VERSION}（由本工具生成）. Copy version.dll", 1)
    for sec, key, val in (
        ("General", "Enabled", "1"),
        ("FrameGeneration", "Engine", engine),
        ("FrameGeneration", "MaxGeneratedFrames", str(mult - 1)),
        ("DLSSG", "Optimized", str(tier)),
        ("DLSSG", "Preset", preset),
        ("Logging", "Level", str(max(0, min(3, int(level))))),
        ("SuperResolution", "Mode", sr_mode),
    ):
        text = _set_ini_value(text, sec, key, val)
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


GAME_SUPPORT_FILES = tuple(
    path for path in PAYLOAD_SHA256
    if path.startswith("dlssg_sm86/") and not path.startswith("dlssg_sm86/logs/")
)

# 部署文件名 → 包内相对路径。替代入口在包里放在 alternatives/ 下，而目标文件
# 直接写在游戏目录根部（如 winmm.dll），所以查哈希前必须先映射回包内路径，
# 否则 PAYLOAD_SHA256 会以部署名做键并抛 KeyError。
_PAYLOAD_REL_BY_ENTRY = {item[1]: item[2] for item in ENTRIES}


def payload_rel(rel: str) -> str:
    """把部署文件名映射到包内相对路径；非入口文件原样返回。"""
    return _PAYLOAD_REL_BY_ENTRY.get(rel, rel)


def _backup_file(source: Path, backup_root: Path, relative: str,
                 backups: dict[str, str]) -> str:
    """Save one existing game file once, without overwriting an earlier rollback copy."""
    existing = backups.get(relative)
    if existing and Path(existing).is_file():
        return existing
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe game path: {relative}")
    dest = backup_root / "original" / rel
    if dest.exists():
        dest = dest.with_name(f"{dest.name}.{time.time_ns()}.bak")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    backups[relative] = str(dest)
    return str(dest)


def _copy_atomic(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def payload_for_entry(entry_name: str, runtime: str = "") -> tuple[Path | None, str]:
    """按入口名 + 运行库版本解析运行包内的源文件路径。

    0.4.x 从随包的 payload/ 取，0.3.5 从解压后的兼容包取；310.1 在 310.1/
    子目录下，310.9 在根目录。
    """
    rt = runtime or DEFAULT_RUNTIME
    src, err = pack_dir(rt)
    if not src:
        return None, err
    prefix = runtime_prefix(rt)
    for item in ENTRIES:
        fname, rel = item[1], item[2]
        if fname.lower() == entry_name.lower():
            p = src / (prefix + rel)
            if p.is_file():
                return p, ""
            return None, tr('运行包缺少 {0}').format(prefix + rel)
    return None, tr('未知入口 {0}').format(entry_name)


def _check_payload_table(root: Path, table: dict[str, str],
                         required: list[str]) -> list[str]:
    """逐文件比对内置 SHA-256 清单；缺失、不可读或哈希不符都算失败。"""
    warns: list[str] = []
    for rel in sorted(required):
        want = table.get(rel)
        if not want:
            warns.append(f"内置清单缺少必要文件：{rel}")
            continue
        p = root / rel
        if not p.is_file():
            warns.append(f"缺少上游文件 {rel}")
            continue
        try:
            got = sha256(p)
        except OSError as e:
            warns.append(f"无法读取上游文件 {rel}: {e}")
            continue
        if got != want:
            warns.append(f"上游文件哈希不符 {rel}（本地 {got[:12]} / 期望 {want[:12]}）")
    return warns


def verify_payload(runtime: str = "") -> list[str]:
    """校验运行包完整性，缺失或被改动的文件都会阻止部署。"""
    rt = runtime or DEFAULT_RUNTIME
    if runtime_is_legacy(rt):
        root, err = ensure_legacy_pack()
        if not root:
            return [err or tr('旧版兼容包无法使用')]
        prefix = runtime_prefix(rt)
        table = PAYLOAD_SHA256_BY_VERSION[LEGACY_UPSTREAM_VERSION]
        required = [prefix + item[2] for item in ENTRIES]
        return _check_payload_table(root, table, required)

    warns: list[str] = []
    src = payload_dir()
    if not src:
        # 附带已查找位置，把哑报错变成可自查（纯诊断文本，不进 i18n 词典）
        tried = "；".join(str(p) for p in payload_search_paths())
        return [tr('未找到运行包目录，无法部署'),
                "已查找位置：" + tried]

    if MOD_VERSION != UPSTREAM_VERSION:
        return [f"程序内置上游版本 {MOD_VERSION} 与清单版本 {UPSTREAM_VERSION} 不一致"]
    if UPSTREAM_ARCHIVE_SHA256 != "7230131637617ede9dc45c552244ddb814ae70098406e102fc254d52bcdb6e14":
        return ["程序内置上游包校验值异常"]
    required = sorted({INI_NAME, *(item[2] for item in ENTRIES), *GAME_SUPPORT_FILES})
    warns.extend(_check_payload_table(src, PAYLOAD_SHA256, required))
    return warns


def _all_known_hashes() -> set[str]:
    """当前 payload 与历史版本的入口哈希合集（识别本项目部署）。

    含两部分：按版本索引的代理模式表（PAYLOAD_SHA256_BY_VERSION，
    0.3.0 ~ 当前）、更早的 native 模式表（PAYLOAD_SHA256_LEGACY）。
    升级部署时据此判定「这是本项目写入的文件」，可直接覆盖而不误判为
    第三方文件 —— 所以历史版本的表不能删，删了老用户升级会被当成占用。
    """
    known = set(PAYLOAD_SHA256_LEGACY.values())
    for table in PAYLOAD_SHA256_BY_VERSION.values():
        known |= set(table.values())
    return known


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
           runtime: str = "", tier: int = DEFAULT_TIER,
           engine: str = "DLSS", preset: str = "A",
           sr_mode: str = "Off") -> tuple[bool, list[str]]:
    """部署所选上游的代理、运行库和配置，并记录可安全恢复的文件。"""
    logs: list[str] = []
    runtime = runtime or DEFAULT_RUNTIME
    if runtime not in [k for k, _p, _d in RUNTIMES]:
        return False, [tr('[错误] 未知运行库版本 {0}').format(runtime)]
    legacy = runtime_is_legacy(runtime)
    engine_key = engine.strip().upper()
    if engine_key not in {"DLSS", "XESS"}:
        return False, [f"Unsupported frame-generation engine: {engine}"]
    engine = "XeSS" if engine_key == "XESS" else "DLSS"
    if legacy and engine != "DLSS":
        logs.append(tr('[提示] 0.3.5 兼容运行库只支持 DLSS-G，已忽略 XeSS-FG 选择。'))
        engine = "DLSS"
    cap = runtime_mult_cap(runtime, engine)
    if int(mult or 2) > cap:
        logs.append(tr('[提示] {0} 上限为 {1}X，已钳制。').format(
            runtime_label(runtime), cap))
        mult = cap

    want_tier = tier
    tier, tier_clamp = clamp_tier(tier, runtime)
    if tier_clamp == "invalid":
        logs.append(tr('[提示] 档位值非法，已按上游行为回退到档位 1。'))
    elif tier_clamp == "runtime_cap":
        logs.append(tr('[提示] {0} 只支持档位 0–1，已把档位 {1} 钳到 {2}。').format(
            runtime_label(runtime), want_tier, tier))
    if legacy:
        logs.append(tr('[提示] 已选择上游 {0} 兼容运行库：单文件代理、运行库内嵌，'
                       '不部署 dlssg_sm86/ 运行库目录。').format(LEGACY_UPSTREAM_VERSION))
    exe_dir = Path(game.exe_dir)
    if not exe_dir.is_dir():
        return False, [tr('[错误] 目录不存在：{0}').format(exe_dir)]

    gpu = detect_gpu()
    driver_match = re.match(r"\s*(\d+)", gpu.driver or "")
    if driver_match and int(driver_match.group(1)) < 580:
        if not legacy:
            return False, [tr('[错误] NVIDIA 驱动 {0} 低于上游要求 R580；已取消部署').format(gpu.driver)]
        logs.append(tr('[提示] NVIDIA 驱动 {0} 低于上游 0.4.x 要求的 R580；'
                       '0.3.5 兼容运行库不要求 R580，继续部署。').format(gpu.driver))
    if not driver_match:
        if legacy:
            logs.append(tr('[提示] 未能读取 NVIDIA 驱动版本；0.3.5 兼容运行库不要求 R580。'))
        else:
            logs.append(tr('[提示] 未能读取 NVIDIA 驱动版本；上游 0.4.x 要求 R580 或更新版本。'))

    warns = verify_payload(runtime)
    if warns:
        return False, [tr('[错误] 上游运行包校验失败，已取消部署。'), *warns]

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
        other_path = exe_dir / other
        if other_path.exists():
            is_project_proxy = False
            if other_path.is_file() and not other_path.is_symlink():
                try:
                    is_project_proxy = sha256(other_path) in _all_known_hashes()
                except OSError:
                    pass
            if not is_project_proxy:
                return False, logs + [tr('[错误] {0} 与 {1} 不能同时存在；'
                                         '请先移除另一个再部署。').format(entry, other)]
        logs.append(tr('[警告] {0} 位于 D3D12 渲染热路径，加载顺序敏感，'
                       '仅在工具类代理都不可用时使用。').format(entry))

    key = game_key(str(exe_dir))
    bdir = backups_dir() / key
    bdir.mkdir(parents=True, exist_ok=True)
    st = load_state()
    rec = dict(st.setdefault("games", {}).get(key, {}))
    old_managed = dict(rec.get("managed_files") or {})
    file_backups = dict(rec.get("file_backups") or {})
    target = exe_dir / entry
    ini_path = exe_dir / INI_NAME
    if ini_path.is_symlink() or (ini_path.exists() and not ini_path.is_file()):
        return False, logs + [f"配置目标不是普通文件，已停止以保护现有内容：{ini_path}"]

    # A previous proxy from this project must not remain beside the newly
    # selected one. Windows may load that older name first and keep running it,
    # making a manual entry switch appear to have no effect. Leave unrelated
    # DLLs untouched.
    stale_entry_files: list[str] = []
    known_proxy_hashes = _all_known_hashes()
    for item in ENTRIES:
        fname = item[1]
        if fname == entry:
            continue
        candidate = exe_dir / fname
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            digest = sha256(candidate)
        except OSError:
            continue
        recorded_owned = (old_managed.get(fname) == digest
                          or (fname == _entry_filename(str(rec.get("entry") or ""))
                              and rec.get("dll_sha256") == digest))
        if recorded_owned or digest in known_proxy_hashes:
            stale_entry_files.append(fname)

    pack_root, pack_err = pack_dir(runtime)
    if not pack_root:
        return False, logs + [tr('[错误] {0}').format(pack_err)]
    support_sources = [(rel, pack_root / rel) for rel in support_files_for(runtime)]
    file_sources = [(entry, src), *support_sources]

    # Files this project wrote for an older deployment may not belong to the
    # selected runtime — 0.4.x ships dlssg_sm86/*, while 0.3.5 embeds the
    # runtime inside the proxy. Remove only files whose current hash still
    # matches the recorded one, so user edits are preserved.
    new_rels = {rel for rel, _source in file_sources}
    stale_support_files: list[str] = []
    for rel, digest in old_managed.items():
        if rel in new_rels or not rel.startswith(LOG_DIR_NAME + "/"):
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        dest = exe_dir / rel_path
        if dest.is_symlink() or not dest.is_file():
            continue
        try:
            if not digest or sha256(dest) != digest:
                continue
        except OSError:
            continue
        stale_support_files.append(rel)

    stale_files = stale_entry_files + stale_support_files
    rels = [rel for rel, _ in file_sources] + stale_files + [INI_NAME]
    if len(set(rels)) != len(rels):
        return False, logs + ["上游运行包的部署路径重复，已取消部署。"]

    for rel in [*(rel for rel, _source in file_sources), *stale_files]:
        dest = exe_dir / Path(rel)
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            return False, logs + [f"目标路径不是普通文件，已停止以保护现有内容：{dest}"]

    try:
        previous_ini = read_text(ini_path) if ini_path.is_file() else ""
        ini_text = build_ini(router, mult, bilinear, level, tier, runtime,
                             engine, preset, sr_mode, previous_ini)
    except Exception as e:
        return False, logs + [tr('[错误] 无法生成上游配置：{0}').format(e)]

    txn = Path(tempfile.mkdtemp(prefix=".deploy-", dir=bdir))
    snapshots: dict[str, Path | None] = {}
    changed: list[str] = []
    try:
        for rel in rels:
            dest = exe_dir / Path(rel)
            if dest.is_file():
                snap = txn / Path(rel)
                snap.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, snap)
                snapshots[rel] = snap
            else:
                snapshots[rel] = None

        # First update: retain any pre-existing files that are not recorded as
        # this manager's last deployment. Old manager state remains supported.
        for rel, source in file_sources:
            dest = exe_dir / Path(rel)
            if not dest.is_file() or sha256(dest) == sha256(source):
                continue
            current_hash = sha256(dest)
            is_recorded = old_managed.get(rel) == current_hash
            is_legacy_entry = rel == rec.get("entry") and current_hash == rec.get("dll_sha256")
            is_known_proxy = rel in {item[1] for item in ENTRIES} and current_hash in _all_known_hashes()
            if not (is_recorded or is_legacy_entry or is_known_proxy):
                _backup_file(dest, bdir, rel, file_backups)
                logs.append(tr('[备份] 原有 {0} → {1}').format(rel, file_backups[rel]))

        if ini_path.is_file() and not rec.get("ini_backup") and INI_NAME not in file_backups:
            manager_ini = (APP_NAME in previous_ini[:4096]
                           and ("生成" in previous_ini[:4096] or "Generated by" in previous_ini[:4096]))
            if not manager_ini:
                _backup_file(ini_path, bdir, INI_NAME, file_backups)
                logs.append(tr('[备份] 原有 {0} → {1}').format(INI_NAME, file_backups[INI_NAME]))

        managed_files: dict[str, str] = {}

        # Remove stale project files before writing the new set. They are
        # included in the transaction snapshot above, so a later failure can
        # restore them exactly. Original-file backups remain in state and are
        # restored by the normal one-click restore flow.
        for rel in stale_files:
            dest = exe_dir / rel
            if not dest.is_file() or dest.is_symlink():
                continue
            current_hash = sha256(dest)
            recorded_owned = (old_managed.get(rel) == current_hash
                              or (rel == _entry_filename(str(rec.get("entry") or ""))
                                  and rec.get("dll_sha256") == current_hash))
            if not recorded_owned and current_hash not in known_proxy_hashes:
                continue
            dest.unlink()
            changed.append(rel)
            logs.append(tr('[移除] {0}').format(rel))
            # If the game originally shipped this file, put it back now instead
            # of leaving a hole until the user clicks Restore.
            original = file_backups.get(rel)
            if original and Path(original).is_file():
                _copy_atomic(Path(original), dest)
                logs.append(tr('[还原] {0} ← 备份').format(rel))

        for rel, source in file_sources:
            dest = exe_dir / Path(rel)
            want = sha256(source)
            if not dest.is_file() or sha256(dest) != want:
                _copy_atomic(source, dest)
                changed.append(rel)
            got = sha256(dest)
            if got != want:
                raise IOError(f"SHA-256 verification failed after writing {rel}")
            managed_files[rel] = want
            logs.append(tr('[写入] {0} → {1}（{2}）').format(rel, dest, size_text(dest.stat().st_size)))

        ini_temp = txn / (INI_NAME + ".new")
        ini_temp.write_text(ini_text, encoding="utf-8", newline="")
        new_ini_hash = sha256(ini_temp)
        if not ini_path.is_file() or sha256(ini_path) != new_ini_hash:
            tmp_target = ini_path.with_name(f".{INI_NAME}.{time.time_ns()}.tmp")
            shutil.copy2(ini_temp, tmp_target)
            os.replace(tmp_target, ini_path)
            changed.append(INI_NAME)
        managed_files[INI_NAME] = sha256(ini_path)

        new_state = dict(rec)
        new_state.update({
            "name": game.name, "exe_dir": str(exe_dir), "exe": game.exe, "entry": entry,
            "dll_sha256": sha256(target), "ini_sha256": sha256(ini_path),
            "managed_files": managed_files, "file_backups": file_backups,
            "installed_at": time.time(), "runtime": runtime,
            "upstream": runtime_upstream(runtime), "engine": engine,
            "mult": mult, "level": level, "tier": tier, "preset": preset,
            "sr_mode": sr_mode, "source": game.source, "gpu_engine": game.engine,
            "dlssg": game.dlssg,
        })
        st["games"][key] = new_state
        save_state(st)
    except PermissionError as e:
        logs.append(tr('[错误] 权限不足或被占用：{0}').format(e))
        logs.append(tr('[提示] 以管理员身份运行本程序，并确认游戏已完全退出'))
    except Exception as e:
        logs.append(tr('[错误] 部署失败：{0}').format(e))
    else:
        shutil.rmtree(txn, ignore_errors=True)
        if legacy:
            # 0.3.5 不读 dlssg_sm86/ 下的运行库；把本次切回后已空掉的旧目录
            # 一并清掉，避免残留文件被误认为仍在生效。logs 里有日志就保留。
            prune_empty_dirs(exe_dir / LOG_DIR_NAME)
        logs.append(f"[配置] Runtime={runtime} ({runtime_upstream(runtime)}), "
                    f"Engine={engine}, MaxGeneratedFrames={mult - 1}, "
                    f"Preset={'Auto' if legacy else preset}, "
                    f"SuperResolution={'Off' if legacy else sr_mode}, "
                    f"Optimized={tier}, Logging={level}")
        if legacy:
            logs.append(tr('[完成] 已启用（{0}，档位 {1}）。重启游戏后进入画面设置，'
                           '打开“帧生成”并选择倍率；该运行库最高 {2}X。').format(
                               runtime_label(runtime), tier, cap))
        else:
            logs.append(tr('[完成] 已启用（{0}，档位 {1}）。重启游戏后进入画面设置，打开“帧生成”并选择倍率；'
                           '游戏支持动态插帧时最高可选 {2}X。').format(
                               runtime_label(runtime), tier, cap))
        return True, logs

    # If any write or state save failed, roll back every target touched by this
    # operation. The transaction copies are separate from long-term backups.
    rollback_errors: list[str] = []
    for rel in reversed(changed):
        dest = exe_dir / Path(rel)
        snapshot = snapshots.get(rel)
        try:
            if snapshot and snapshot.is_file():
                _copy_atomic(snapshot, dest)
            elif dest.is_file():
                dest.unlink()
        except Exception as rollback_error:
            rollback_errors.append(f"{rel}: {rollback_error}")
    shutil.rmtree(txn, ignore_errors=True)
    if rollback_errors:
        logs.append("回滚未完全成功：" + "; ".join(rollback_errors))
    return False, logs


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
    removed = 0
    complete = True
    managed = dict(rec.get("managed_files") or {})
    if not managed:
        entry = rec.get("entry", "")
        if entry:
            managed[entry] = rec.get("dll_sha256", "")
        ini = exe_dir / INI_NAME
        if ini.is_file():
            try:
                head = read_text(ini)[:4096]
                if (APP_NAME in head and
                        ("生成" in head or "Generated by" in head)):
                    managed[INI_NAME] = rec.get("ini_sha256", "")
            except OSError:
                pass

    for rel, expected in managed.items():
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts:
            logs.append(f"[跳过] 状态记录含不安全路径：{rel}")
            complete = False
            continue
        target = exe_dir / path
        if not target.is_file():
            continue
        try:
            current = sha256(target)
            if expected:
                is_owned = current == expected
            elif rel == INI_NAME:
                head = read_text(target)[:4096]
                is_owned = APP_NAME in head and ("生成" in head or "Generated by" in head)
            else:
                is_owned = rel in {item[1] for item in ENTRIES} and current in _all_known_hashes()
            if is_owned:
                target.unlink()
                removed += 1
                logs.append(tr('[移除] {0}').format(rel))
            else:
                logs.append(tr('[跳过] {0} 已被替换或修改，为安全起见保留').format(rel))
                complete = False
        except OSError as e:
            logs.append(tr('[错误] 无法移除 {0}：{1}').format(rel, e))
            complete = False

    # Older installs may have several project proxies but only one recorded
    # in state. Remove any remaining known proxy names before restoring the
    # original files from file_backups.
    known_proxy_hashes = _all_known_hashes()
    for item in ENTRIES:
        fname = item[1]
        target = exe_dir / fname
        if not target.is_file() or target.is_symlink():
            continue
        try:
            if sha256(target) not in known_proxy_hashes:
                continue
            target.unlink()
            removed += 1
            logs.append(tr('[移除] {0}').format(fname))
        except OSError as e:
            logs.append(tr('[错误] 无法移除 {0}：{1}').format(fname, e))
            complete = False

    # 0.3.5 不读 dlssg_sm86/ 运行库目录；移除本工具写入的文件后，
    # 把空掉的旧目录树一并修剪（有日志或用户文件时保留）。
    prune_empty_dirs(exe_dir / LOG_DIR_NAME)

    backup_root = (backups_dir() / key).resolve()

    def restore_backup(rel: str, backup: str) -> None:
        nonlocal complete
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts:
            logs.append(f"[跳过] 备份记录含不安全路径：{rel}")
            complete = False
            return
        source = Path(backup).resolve()
        try:
            source.relative_to(backup_root)
        except ValueError:
            logs.append(f"[跳过] 备份位置不在本工具备份目录内：{backup}")
            complete = False
            return
        if not source.is_file():
            return
        target = exe_dir / path
        if target.exists():
            logs.append(tr('[跳过] {0} 已有文件，保留当前内容以免覆盖').format(rel))
            complete = False
            return
        try:
            _copy_atomic(source, target)
            logs.append(tr('[还原] {0} ← 备份').format(rel))
        except Exception as e:
            logs.append(tr('[错误] 还原 {0} 失败：{1}').format(rel, e))
            complete = False

    for rel, backup in (rec.get("file_backups") or {}).items():
        restore_backup(rel, backup)
    for fname, backup in (rec.get("backups") or {}).items():
        # Legacy records only contained a top-level proxy DLL name.
        restore_backup(fname, backup)
    if rec.get("ini_backup"):
        restore_backup(INI_NAME, rec["ini_backup"])

    if complete:
        st.setdefault("games", {}).pop(key, None)
        save_state(st)
    elif removed == 0:
        logs.append("部分修改后的文件仍在原处，状态记录已保留，检查并重试恢复即可。")
    if removed == 0 and complete:
        logs.append(tr('[信息] 没有发现需要移除的文件'))
    if complete:
        logs.append(tr('[完成] 已恢复到部署前的状态；游戏自带的 DLSSG 文件未受影响'))
    return complete, logs


def read_deployed_config(exe_dir: str) -> dict:
    f = Path(exe_dir) / INI_NAME
    if not f.is_file():
        return {}
    txt = read_text(f)
    cfg: dict[str, str | int] = {}
    section = ""
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        if "=" not in stripped:
            continue
        key, value = (part.strip() for part in stripped.split("=", 1))
        if not key or not value:
            continue
        if key in {"Router", "KernelImage", "HardwareBilinear", "MaxGeneratedFrames", "Level",
                   "Enabled", "Optimized", "OptimizedKernels", "Preset", "ImageApprox",
                   "SkipRepeatedRealCopy", "Engine", "Mode"}:
            cfg[key] = value
        cfg[f"{section}.{key}"] = value
    if "FrameGeneration.Engine" in cfg:
        cfg["Engine"] = cfg["FrameGeneration.Engine"]
    if "DLSSG.Preset" in cfg:
        cfg["Preset"] = cfg["DLSSG.Preset"]
    if "SuperResolution.Mode" in cfg:
        cfg["SRMode"] = cfg["SuperResolution.Mode"]
    # 0.3.5 把预设放在 [Compatibility] Preset，且只有 Auto。
    if "Preset" not in cfg and "Compatibility.Preset" in cfg:
        cfg["Preset"] = cfg["Compatibility.Preset"]
    # Both the legacy [FrameGeneration] Optimized and 0.4.x [DLSSG] Optimized are supported.
    raw = cfg.get("DLSSG.Optimized") or cfg.get("Optimized") or cfg.get("OptimizedKernels")
    if raw is not None:
        try:
            t = int(raw)
            cfg["tier"] = t if TIER_MIN <= t <= TIER_MAX else DEFAULT_TIER
        except ValueError:
            cfg["tier"] = DEFAULT_TIER
    return cfg


# ---------------------------------------------------------------- 汇总

SCAN_MAX_WORKERS = 4


def _analyze_game_root(row: tuple[int, str, str, str], state_games: dict) -> tuple[int, Game | None]:
    """Read-only analysis for one game root; safe to run in a bounded worker pool."""
    index, name, path, source = row
    cands = find_candidates(path)
    if not cands:
        return index, None
    best = cands[0]
    exe_dir_c = canon_dir(best.exe_dir)
    game = Game(gid=game_key(exe_dir_c), name=name, source=source,
                install_dir=canon_dir(path), exe=canon_dir(best.exe), exe_dir=exe_dir_c,
                engine=best.engine, dlssg=best.dlssg, dlss=best.dlss,
                candidates=[asdict(candidate) for candidate in cands])
    game.anticheat = detect_anticheat(path)
    record = state_games.get(game.gid)
    entry, ours = entry_of_deployment(best.exe_dir)
    game.deployed = bool(record) and bool(entry) and ours
    game.entry = entry or (record or {}).get("entry", "")
    game.installed_at = (record or {}).get("installed_at", 0)
    game.config = read_deployed_config(best.exe_dir)
    if record:
        # 运行库版本不在 INI 里（旧格式没有该键），从部署状态回显。
        game.config["__runtime__"] = record.get("runtime") or ""
        game.config["__upstream__"] = record.get("upstream") or runtime_upstream(
            record.get("runtime") or "")
    game.resolution = guess_resolution(best.exe_dir, name, best.exe)
    return index, game

def collect_games(state: dict, progress=None, extra: list[tuple[str, str, str]] | None = None,
                  deep_roots: list[str] | None = None, deep_budget: float = 75.0) -> list[Game]:
    """汇总所有来源 → 定位渲染 EXE → 返回游戏列表。"""
    ignored_gids, ignored_install_dirs, ignored_exe_dirs = _ignored_game_indexes(state)
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
        try:
            k = norm(canon_dir(path))
        except Exception:
            k = norm(path)
        if k in ignored_install_dirs:
            continue
        if k in seen:
            continue
        seen.add(k)
        uniq.append((name, path, source))

    total = len(uniq)
    analyzed: list[Game | None] = [None] * total
    if total:
        worker_count = min(SCAN_MAX_WORKERS, total)
        indexed_rows = [(i, name, path, source) for i, (name, path, source) in enumerate(uniq)]
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="dlssg-scan") as pool:
            pending = {pool.submit(_analyze_game_root, row, state.get("games", {})): row[0]
                       for row in indexed_rows}
            completed = 0
            if progress:
                progress(tr('正在分析渲染进程… {0}/{1}').format(0, total))
            for future in as_completed(pending):
                index, game = future.result()
                if game is not None and (
                    str(game.gid) in ignored_gids
                    or norm(canon_dir(game.install_dir)) in ignored_install_dirs
                    or norm(canon_dir(game.exe_dir)) in ignored_exe_dirs
                ):
                    game = None
                analyzed[index] = game
                completed += 1
                if progress and (completed % 2 == 0 or completed == total):
                    progress(tr('正在分析渲染进程… {0}/{1}').format(completed, total))
    games = [game for game in analyzed if game is not None]

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
        engine = argv[argv.index("--engine") + 1] if "--engine" in argv else "DLSS"
        preset = argv[argv.index("--preset") + 1] if "--preset" in argv else "A"
        sr_mode = argv[argv.index("--sr") + 1] if "--sr" in argv else "Off"
        g = Game(name=Path(target).name, exe_dir=canon_dir(target))
        ok, logs = deploy(g, router, mult, "--bilinear" in argv, 1, entry, bool(entry),
                          runtime, tier, engine, preset, sr_mode)
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
        info = check_update()
        print(json.dumps(asdict(info), ensure_ascii=False, indent=2))
        return 0 if info.ok else 1

    print(f"{APP_NAME} {APP_VERSION}")
    print("  --gpu                 显示显卡探测结果")
    print("  --update              检查是否有新版本")
    print("  --hags [--on|--off]   查看 / 开启 / 关闭硬件加速 GPU 计划")
    print("  --scan [--deep <盘符>] 扫描游戏并输出 JSON")
    print("  --install <EXE目录> [--router SM86|SM75] [--mult 2|3|4] [--bilinear]"
          " [--entry <入口>] [--runtime 310.9.16] [--tier 0|1|2|3]"
          " [--engine DLSS|XeSS] [--preset A|B|C] [--sr Off|M-INT8|L-INT8|M-FP16|L-FP16]")
    print("  --restore <EXE目录>")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
