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
