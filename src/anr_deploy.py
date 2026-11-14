r"""ANR FG 侧载部署 / 还原（平铺布局，不需要 OptiScaler）。

布局依据（二进制证据）：nvngx_dlssg.dll 通过 GetModuleFileNameA/W 取自身路径，
再拼 `\path_table.json`、`\programs\fg-lite-*` 等，所以资源必须**和 DLL 同级**。
侧载时 DLL 要落在游戏根目录（游戏按名字加载 nvngx_dlssg.dll），因此整套
资源也平铺到游戏根目录 —— 这就是本模块做的事。

安全性：
- 目标位置已有同名文件（例如游戏自带的 nvngx_dlssg.dll）→ 先备份再覆盖，记进 record
- restore 只删「我们写过且内容没被改过」的文件，然后还原备份
- 全程只碰 needs 里列出的相对路径，不做通配删除
"""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

import anr_profile as anr

MAIN_DLL = "nvngx_dlssg.dll"
PROXY_INI = "dlssg_sm86.ini"
PROXY_RUNTIME = Path("dlssg_sm86") / "runtime"


STREAMLINE_REL = Path("Engine") / "Plugins" / "Runtime" / "Nvidia" / "StreamlineCore" / "Binaries" / "ThirdParty" / "Win64"
STREAMLINE_DLL = "nvngx_dlssg.dll"


def find_layout(game_dir) -> tuple[str, Path]:
    r"""找出「游戏真正加载 nvngx_dlssg.dll 的位置」，返回 (布局名, 相对游戏根的目录)。

    实测 Phantom Blade Zero：
    · exe 目录里平铺 nvngx_dlssg.dll → 游戏完全不加载（没有任何日志）
    · 游戏真正用的是 UE5 Streamline 插件目录里的那份：
      Engine\Plugins\Runtime\Nvidia\StreamlineCore\Binaries\ThirdParty\Win64\nvngx_dlssg.dll
    所以优先替换那个槽位；其次才考虑我们自己的代理（dlssg_sm86\runtime\），最后才是平铺。
    """
    base = Path(game_dir)
    here = base
    for _ in range(5):                      # 往上最多找 5 层，覆盖 platform\steam → 游戏根
        slot = here / STREAMLINE_REL
        if (slot / STREAMLINE_DLL).is_file():
            try:
                return "streamline", slot.relative_to(base)
            except ValueError:
                return "streamline", slot
        if here.parent == here:
            break
        here = here.parent
    if (base / PROXY_INI).is_file() and (base / PROXY_RUNTIME).is_dir():
        return "proxy", PROXY_RUNTIME
    return "flat", Path("")


def _copy(src, dst, tries: int = 20) -> None:
    """复制文件；被占用（杀软扫描 / 游戏还在跑）时重试几次，最后给一句人话。"""
    for attempt in range(tries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError as exc:
            if attempt == tries - 1:
                raise RuntimeError(
                    f"文件被占用，复制失败：{Path(dst).name} —— 请先完全退出游戏再试"
                ) from exc
            time.sleep(0.25)


def detect_layout(game_dir) -> str:
    """选部署位置。

    - proxy：游戏里已经有本工具的代理（dlssg_sm86.ini + dlssg_sm86\runtime\）。
      这时游戏加载 nvngx_dlssg.dll 是从 dlssg_sm86\runtime\ 走的，ANR 必须放到那里，
      否则游戏根本看不到它（实测：平铺到 exe 根目录 + 代理存在 = 永远不加载）。
    - flat：没有代理，直接平铺到 exe 根目录。
    """
    base = Path(game_dir)
    if (base / PROXY_INI).is_file() and (base / PROXY_RUNTIME).is_dir():
        return "proxy"
    return "flat"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def plan(plugin_dir, root: Path = Path("")) -> list[tuple[Path, Path]]:
    """(源文件, 游戏目录里的相对路径)。

    ANR 的所有资源都必须和它的 DLL 同级（它用 GetModuleFileName 按自身目录找），
    所以换布局时是整体搬一个文件夹，而不是只换 DLL 的位置。
    """
    base = Path(plugin_dir)
    root = Path(root)
    pairs: list[tuple[Path, Path]] = [(base / MAIN_DLL, root / MAIN_DLL)]
    for name in anr.SUPPORT_FILES:
        pairs.append((base / name, root / name))
    for name in anr.SUPPORT_DIRS:
        for f in sorted((base / name).rglob("*")):
            if f.is_file():
                pairs.append((f, root / f.relative_to(base)))
    return pairs


def deploy(game_dir, plugin_dir, backup_root) -> dict:
    """把 ANR 平铺进游戏目录，返回可持久化的部署记录。"""
    base = Path(game_dir)
    if not base.is_dir():
        raise NotADirectoryError(f"游戏目录不存在: {base}")
    missing = anr.check_layout(plugin_dir)
    if missing:
        raise ValueError("ANR 源目录不完整，缺少: " + ", ".join(missing))

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = Path(backup_root) / f"anr-{stamp}"
    layout, root = find_layout(base)
    record: dict = {"layout": layout, "root": root.as_posix(), "installed_at": int(time.time()),
                    "backup_dir": str(backup_dir), "files": [], "backups": {}}

    for src, rel in plan(plugin_dir, root):
        dst = base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            # rel 可能是绝对路径（Streamline 槽位在 exe 目录之外），
            # 直接 backup_dir / 绝对路径 会得到它自己 —— 那会把文件复制到自己身上。
            backup_rel = rel if not rel.is_absolute() else Path(*rel.parts[1:])
            backup = backup_dir / backup_rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            _copy(dst, backup)
            record["backups"][rel.as_posix()] = str(backup)
        shutil.copy2(src, dst)
        record["files"].append({"path": rel.as_posix(), "sha256": sha256_file(dst)})
    return record


def restore(game_dir, record) -> list[str]:
    """按部署记录还原；返回给人看的操作日志。"""
    base = Path(game_dir)
    log: list[str] = []

    for item in record.get("files", []):
        dst = base / item["path"]
        if not dst.exists():
            continue
        if sha256_file(dst) != item.get("sha256"):
            log.append(f"跳过（已被改动）：{item['path']}")
            continue
        dst.unlink()
        log.append(f"删除 {item['path']}")

    roots = [base, base / PROXY_RUNTIME, base / str(record.get("root") or "")]
    for root in {r for r in roots}:
        for name in anr.SUPPORT_DIRS:
            folder = root / name
            if folder.is_dir() and not any(p.is_file() for p in folder.rglob("*")):
                shutil.rmtree(folder, ignore_errors=True)
                try:
                    shown = folder.relative_to(base)
                except ValueError:
                    shown = folder          # Streamline 槽位在 exe 目录之外
                log.append(f"删除空目录 {shown}/")

    for rel, backup in record.get("backups", {}).items():
        src = Path(backup)
        dst = base / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            _copy(src, dst)
            log.append(f"还原 {rel}")

    return log


def default_source_dir(root) -> Path | None:
    """找一个可用的 ANR 源目录（优先随包 payload，其次 build 里的侧载产出）。"""
    root = Path(root)
    candidates = (
        root / "payload" / "anr-fg" / "dlssg",
        root / "build" / "anr_sideload" / "dlssg",
    )
    for cand in candidates:
        if cand.is_dir() and not anr.check_layout(cand):
            return cand
    return None
