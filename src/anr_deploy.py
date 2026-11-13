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


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def plan(plugin_dir) -> list[tuple[Path, Path]]:
    """(源文件, 游戏目录里的相对路径)。DLL 与全部资源都平铺到游戏根。"""
    base = Path(plugin_dir)
    pairs: list[tuple[Path, Path]] = [(base / MAIN_DLL, Path(MAIN_DLL))]
    for name in anr.SUPPORT_FILES:
        pairs.append((base / name, Path(name)))
    for name in anr.SUPPORT_DIRS:
        for f in sorted((base / name).rglob("*")):
            if f.is_file():
                pairs.append((f, f.relative_to(base)))
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
    record: dict = {"layout": "flat", "installed_at": int(time.time()),
                    "backup_dir": str(backup_dir), "files": [], "backups": {}}

    for src, rel in plan(plugin_dir):
        dst = base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            backup = backup_dir / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup)
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

    for name in anr.SUPPORT_DIRS:
        folder = base / name
        if folder.is_dir() and not any(p.is_file() for p in folder.rglob("*")):
            shutil.rmtree(folder, ignore_errors=True)
            log.append(f"删除空目录 {name}/")

    for rel, backup in record.get("backups", {}).items():
        src = Path(backup)
        dst = base / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
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
