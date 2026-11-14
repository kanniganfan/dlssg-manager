"""ANR FG（Apex Neural Rendering）参数模型 —— 读写游戏目录里的 nr_fg.ini。

ANR 官方只有两个入口：OptiScaler 的菜单，或者直接改 `nr_fg.ini`（改完要重启游戏）。
这里把那个 ini 变成可校验的数据模型，界面就能直接调参数，用户不用记键名。

约定：数值一律钳制、非法键回退默认 —— 一份手改坏的 ini 不该让整个游戏列表崩掉。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path

# ANR 在游戏目录里的落点：官方包用 OptiScaler 的 custom 插件目录
PLUGIN_DIR = Path("OptiScaler") / "custom" / "Apex Neural Rendering FG"
INI_RELPATH = PLUGIN_DIR / "dlssg" / "nr_fg.ini"
# 侧载（不走 OptiScaler）时我们自己的布局
SIDELOAD_INI_RELPATH = Path("anr_fg") / "dlssg" / "nr_fg.ini"

# 卷积路径：auto = 按显卡自选；其余是强制指定，说明照抄官方 ini
PATHS = ("auto", "coopmat", "packed", "dp4a", "portable", "portable-linalg", "portable-xmx")
PATH_LABELS = {
    "auto": "自动（按显卡挑最优）",
    "coopmat": "coopmat（矩阵核心，最快）",
    "packed": "packed（打包路径）",
    "dp4a": "dp4a（INT8，最省算力）",
    "portable": "portable（兼容优先）",
    "portable-linalg": "portable-linalg（兼容 + 线性代数）",
    "portable-xmx": "portable-xmx（兼容 + 扩展矩阵）",
}

# 三档预设 → path；高级用户仍可直接选原始路径
PRESETS = {
    "efficiency": "dp4a",
    "balanced": "packed",
    "quality": "coopmat",
}

MULT_MIN, MULT_MAX = 2, 6                     # 界面上的 2X–6X
MAX_GENERATED_MIN, MAX_GENERATED_MAX = 1, 5   # 官方 ini：max_generated = 每帧额外生成的帧数（5 → 6X）
NITS_MIN, NITS_MAX, NITS_DEFAULT = 40, 1000, 80
DEFAULT_PATH = "auto"
DEFAULT_MODEL_SIZE = "large"

# 我们负责写回的键；其余键（例如 ANR 自己的 nvidia_dlssg）原样保留
KNOWN_KEYS = ("build", "path", "model_size", "model_note",
              "nits_per_unit", "max_generated", "scene_cut")

# DLL 按自身所在目录找这些资源（它 import 了 GetModuleFileNameA/W，
# 并拼 "\\path_table.json"、"\\programs\\fg-lite-*"），所以它们必须和 DLL 同级。
SUPPORT_DIRS = ("programs", "kernels", "kernels-portable", "adapters")
SUPPORT_FILES = ("path_table.json", "size_table.json", "nr_fg.ini")


def mult_to_max_generated(mult: int) -> int:
    """界面倍率（2X–6X）→ ini 的 max_generated（1–5，官方语义：每帧额外生成几帧）。"""
    return max(MULT_MIN, min(MULT_MAX, int(mult))) - 1


def max_generated_to_mult(value: int) -> int:
    """ini 的 max_generated（1–5）→ 界面倍率（2X–6X）。"""
    return max(MAX_GENERATED_MIN, min(MAX_GENERATED_MAX, int(value))) + 1


def _as_bool(raw: str, default: bool) -> bool:
    text = (raw or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _as_int(raw: str, default: int, low: int, high: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


@dataclass(frozen=True)
class AnrProfile:
    """nr_fg.ini 里对我们有用的那几个键。"""

    path: str = DEFAULT_PATH
    max_generated: int = MAX_GENERATED_MAX
    scene_cut: bool = True
    nits_per_unit: int = NITS_DEFAULT
    model_size: str = DEFAULT_MODEL_SIZE

    @property
    def mult(self) -> int:
        return max_generated_to_mult(self.max_generated)

    def with_mult(self, mult: int) -> "AnrProfile":
        return replace(self, max_generated=mult_to_max_generated(mult))

    def normalized(self) -> "AnrProfile":
        """钳制所有字段：手改坏的 ini、缺键的旧版本，都能落成一个可用配置。"""
        path = self.path if self.path in PATHS else DEFAULT_PATH
        model_size = (self.model_size or DEFAULT_MODEL_SIZE).strip() or DEFAULT_MODEL_SIZE
        return AnrProfile(
            path=path,
            max_generated=max(MAX_GENERATED_MIN, min(MAX_GENERATED_MAX, int(self.max_generated))),
            scene_cut=bool(self.scene_cut),
            nits_per_unit=max(NITS_MIN, min(NITS_MAX, int(self.nits_per_unit))),
            model_size=model_size,
        )

    @classmethod
    def from_ini_text(cls, text: str) -> "AnrProfile":
        values: dict[str, str] = {}
        for line in (text or "").splitlines():
            stripped = line.strip()
            if not stripped or stripped[0] in ";#":
                continue
            key, sep, raw = stripped.partition("=")
            if not sep:
                continue
            values[key.strip()] = raw.strip()
        default = cls()
        return cls(
            path=values.get("path", default.path).strip() or default.path,
            max_generated=_as_int(values.get("max_generated", default.max_generated),
                                  default.max_generated, MAX_GENERATED_MIN, MAX_GENERATED_MAX),
            scene_cut=_as_bool(values.get("scene_cut", ""), default.scene_cut),
            nits_per_unit=_as_int(values.get("nits_per_unit", default.nits_per_unit),
                                  default.nits_per_unit, NITS_MIN, NITS_MAX),
            model_size=values.get("model_size", default.model_size).strip() or DEFAULT_MODEL_SIZE,
        ).normalized()

    def to_ini_text(self, extras: dict[str, str] | None = None) -> str:
        """写成 ANR 认识的裸 ini，键名与官方包一字不差。

        extras 是用户自己加的键（例如 `nvidia_dlssg = off`）：ANR 会解析，
        我们重写配置时不能把它们弄丢。
        """
        profile = self.normalized()
        tail = "".join(f"{k} = {v}\n" for k, v in (extras or {}).items())
        return (
            "; ANR FG (Apex Neural Rendering). Restart the game after a change.\n"
            "; 由 DLSSG Manager 写入；想恢复默认就删掉本文件，游戏会自己重建。\n"
            "build = user\n"
            f"path = {profile.path}\n"
            f"model_size = {profile.model_size}\n"
            f"nits_per_unit = {profile.nits_per_unit}\n"
            f"max_generated = {profile.max_generated}\n"
            f"scene_cut = {1 if profile.scene_cut else 0}\n"
            + tail
        )


@dataclass(frozen=True)
class AnrInstall:
    """在某个游戏目录里找到的 ANR 安装。"""

    ini_path: Path
    layout: str          # "optiscaler"（官方包）或 "sideload"（我们自己的布局）

    @property
    def plugin_dir(self) -> Path:
        return self.ini_path.parent.parent


def parse_extras(text: str) -> dict[str, str]:
    """取出 ini 里我们不管的键，供重写时原样带回。"""
    extras: dict[str, str] = {}
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in ";#":
            continue
        key, sep, raw = stripped.partition("=")
        key = key.strip()
        if not sep or not key or key in KNOWN_KEYS:
            continue
        extras[key] = raw.strip()
    return extras


def check_layout(plugin_dir) -> list[str]:
    """检查一个 ANR 插件目录是否完整（DLL 与资源必须同级）。"""
    base = Path(plugin_dir)
    missing = [name for name in SUPPORT_FILES if not (base / name).is_file()]
    missing += [f"{name}/" for name in SUPPORT_DIRS if not (base / name).is_dir()]
    if not (base / "nvngx_dlssg.dll").is_file():
        missing.insert(0, "nvngx_dlssg.dll")
    return missing


def load_profile(ini_path) -> AnrProfile:
    """读游戏里的 nr_fg.ini；文件不存在或读不了就回默认值。"""
    try:
        return AnrProfile.from_ini_text(Path(ini_path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return AnrProfile()


def save_profile(ini_path, profile: AnrProfile) -> None:
    """原子写 + 留一份 .bak（ANR 官方安装器也是这么干的）。"""
    p = Path(ini_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    extras: dict[str, str] = {}
    if p.exists():
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
        try:
            extras = parse_extras(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            extras = {}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(profile.to_ini_text(extras), encoding="utf-8", newline="\n")
    tmp.replace(p)


def detect_install(game_exe_dir) -> AnrInstall | None:
    """只读探测：这个游戏目录里装了 ANR 吗？"""
    if not game_exe_dir:
        return None
    base = Path(game_exe_dir)
    for rel, layout in ((INI_RELPATH, "optiscaler"), (SIDELOAD_INI_RELPATH, "sideload")):
        candidate = base / rel
        if candidate.is_file():
            return AnrInstall(ini_path=candidate, layout=layout)
    return None


# ---------------------------------------------------------------- 官方数据表
# ANR 自带两张表：path_table.json（厂商/架构 → 卷积路径）、size_table.json
# （架构 × 分辨率 → 推荐路径 + 允许倍率区间，并标明实测还是预测）。
# 这里只读它们，用来在界面上给出「你的卡该用哪条路径、能不能开这个倍率」。

SIZE_CLASSES = (("1080p", 2073600), ("1440p", 3686400), ("2160p", 0))

# 显卡名 → (厂商, 架构)，与官方 path_table.json 里的 architectures 对齐。
_GPU_HINTS = (
    (r"rtx\s*50\d0", "nvidia", "blackwell"),
    (r"rtx\s*40\d0", "nvidia", "ada"),
    (r"rtx\s*30\d0", "nvidia", "ampere"),
    (r"rtx\s*20\d0", "nvidia", "turing"),
    (r"gtx\s*16\d0", "nvidia", "turing"),
    (r"rx\s*9\d{3}", "amd", "rdna4"),
    (r"rx\s*7\d{3}", "amd", "rdna3"),
    (r"rx\s*6\d{3}", "amd", "rdna2"),
    (r"steam\s*deck", "amd", "rdna2-steam-deck"),
)


@dataclass(frozen=True)
class Recommendation:
    """针对某块显卡 + 某个输出分辨率给出的建议。"""

    vendor: str
    architecture: str
    path: str
    mult_min: int
    mult_max: int
    source: str = ""          # measured / prediction
    note: str = ""

    @property
    def text(self) -> str:
        span = f"{self.mult_min}X–{self.mult_max}X" if self.mult_min != self.mult_max else f"{self.mult_min}X"
        flag = "实测" if self.source == "measured" else ("预测" if self.source == "prediction" else "")
        return f"{self.path}｜{span}｜{self.architecture}" + (f"（{flag}）" if flag else "")


def gpu_arch(gpu_name: str) -> tuple[str, str] | None:
    """把显卡名映射成 (厂商, 架构)；认不出来就返回 None。"""
    import re as _re
    text = (gpu_name or "").lower()
    for pattern, vendor, arch in _GPU_HINTS:
        if _re.search(pattern, text):
            return vendor, arch
    return None


def size_class(width: int, height: int) -> str:
    pixels = max(0, int(width)) * max(0, int(height))
    for name, limit in SIZE_CLASSES:
        if limit == 0 or pixels <= limit:
            return name
    return SIZE_CLASSES[-1][0]


def read_tables(plugin_dir) -> dict:
    """读官方两张表；文件缺失或坏了就返回空字典（界面据此降级）。"""
    import json as _json

    base = Path(plugin_dir)
    tables: dict = {}
    for name in ("path_table.json", "size_table.json"):
        try:
            tables[name] = _json.loads((base / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tables[name] = {}
    return tables


def recommend(plugin_dir, gpu_name: str, width: int, height: int) -> Recommendation | None:
    """按官方 size_table 推荐路径与倍率区间；没有数据就返回 None。"""
    arch_pair = gpu_arch(gpu_name)
    if arch_pair is None:
        return None
    vendor, arch = arch_pair
    tables = read_tables(plugin_dir)
    sizes = tables.get("size_table.json") or {}
    cls = size_class(width, height)

    fallback: Recommendation | None = None
    for entry in sizes.get("entries", []):
        if entry.get("vendor") != vendor or entry.get("architecture") != arch:
            continue
        path = str(entry.get("path") or DEFAULT_PATH)
        source = str(entry.get("source") or "")
        windows = (entry.get("large") or {})
        span = windows.get(cls) or (windows.get("2160p") or windows.get("1440p") or windows.get("1080p"))
        if not span:
            continue
        lo, hi = int(span[0]), int(span[1])
        rec = Recommendation(vendor, arch, path, lo, hi, source, cls)
        if windows.get(cls):
            return rec
        fallback = fallback or rec
    return fallback


# ---------------------------------------------------------------- 运行日志（诊断用）
# ANR 会写两种文件：nr_fg-*.log（文本，含 MultiFrameCountMax / multiplier / path 等）
# 和每帧 CSV（time_ms,requested_generator,host_generation_enabled,...）。
# 游戏设置里能选几倍，最终看它向 DLSS-G 请求的 multiplier —— 只能从这些日志里看到。

LOG_PATTERNS = ("nr_fg*.log", "nr_fg*.csv")
LOG_KEYWORDS = ("multiframe", "multiplier", "requested", "path", "max_generated",
                "generated", "error", "fail", "unavailable", "dlssg", "presentation")


def find_logs(game_dir, limit: int = 4, extra_dirs=()) -> list[Path]:
    """在游戏目录（以及部署记录里的槽位目录）找最新的 ANR 日志。"""
    bases = [Path(game_dir)] + [Path(d) for d in extra_dirs]
    found: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for pattern in LOG_PATTERNS:
            found.extend(base.glob(pattern))
            for sub in ("anr_fg", "dlssg"):
                folder = base / sub
                if folder.is_dir():
                    found.extend(folder.rglob(pattern))
    logs = [f for f in found if f.is_file()]
    logs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return logs[:limit]


def summarize_log(path, max_lines: int = 40) -> list[str]:
    """挑出日志里和「倍率 / 路径 / 报错」相关的行。"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    picked = [ln for ln in lines if any(k in ln.lower() for k in LOG_KEYWORDS)]
    return (picked or lines)[-max_lines:]
