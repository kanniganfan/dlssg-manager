#!/usr/bin/env python3
"""Regression check: a user-added folder must be scanned as a whole library.

此前手动添加目录只做「要么自己算一个游戏、要么只看一层子目录」的二选一：
库目录根上散落一个 setup.exe 就只认出 1 个游戏；游戏要是再深一层
（`库/Steam/游戏A`）整棵树会被并成 1 个条目。这里把几种真实目录结构钉住。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import core  # noqa: E402


def make_exe(path: Path, megabytes: int = 40) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.seek(megabytes * 1024 * 1024 - 1)
        stream.write(b"\0")


def scan(root: Path) -> list[str]:
    state = {"games": {}, "roots": [str(root)], "ignored_games": [], "settings": {}}
    return [game.name for game in core.collect_games(state)]


def main() -> int:
    original = (core.scan_steam, core.scan_epic, core.scan_gog, core.scan_ubisoft)
    core.scan_steam = core.scan_epic = core.scan_gog = core.scan_ubisoft = lambda: []
    # 合成目录必须放在仓库 build/ 下：%TEMP% 与 AppData 在 DIR_BLACKLIST 里，
    # 放到系统临时目录会让所有 EXE 都被当成黑名单文件。
    build_dir = Path(__file__).resolve().parent.parent / "build"
    build_dir.mkdir(exist_ok=True)
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="dlssg_import_", dir=build_dir) as temp:
            base = Path(temp)

            # 1) 库目录：根上散落一个 setup.exe，三个游戏各占一层
            lib = base / "LibraryWithStraySetup"
            make_exe(lib / "setup.exe", 6)
            for name in ("AlanWake2", "Control", "DeathStranding"):
                make_exe(lib / name / "Binaries" / "Win64" / f"{name}-Win64-Shipping.exe")
            got = scan(lib)
            if sorted(got) != ["AlanWake2", "Control", "DeathStranding"]:
                failures.append(f"library with stray setup.exe -> {got}")

            # 2) 游戏藏在库目录下两层
            deep = base / "DeepLibrary"
            for name in ("Hades", "Celeste", "Hollow"):
                make_exe(deep / "Steam" / name / "Binaries" / "Win64" / f"{name}-Win64-Shipping.exe")
            got = scan(deep)
            if sorted(got) != ["Celeste", "Hades", "Hollow"]:
                failures.append(f"games nested two levels deep -> {got}")

            # 3) 单个游戏目录（Binaries/Win64 结构）
            single = base / "SingleGame"
            make_exe(single / "Binaries" / "Win64" / "SingleGame-Win64-Shipping.exe")
            got = scan(single)
            if got != ["SingleGame"]:
                failures.append(f"single UE game dir -> {got}")

            # 4) 单个游戏目录（EXE 就在根上）
            flat = base / "FlatGame"
            make_exe(flat / "FlatGame.exe")
            got = scan(flat)
            if got != ["FlatGame"]:
                failures.append(f"single flat game dir -> {got}")

            # 5) 空目录：不报错、不出条目
            empty = base / "Empty"
            empty.mkdir()
            got = scan(empty)
            if got:
                failures.append(f"empty dir -> {got}")

            # 6) 一个库里混着「根上就是 EXE 的游戏」和「UE 结构的游戏」
            mixed = base / "MixedLibrary"
            make_exe(mixed / "Starfield" / "Starfield.exe")
            make_exe(mixed / "Blasphemous" / "Binaries" / "Win64" / "Blasphemous-Win64-Shipping.exe")
            got = scan(mixed)
            if sorted(got) != ["Blasphemous", "Starfield"]:
                failures.append(f"mixed library -> {got}")

            # 7) 同一目录重复添加不应出重复条目
            state = {"games": {}, "roots": [str(lib), str(lib)], "ignored_games": [], "settings": {}}
            dup = [game.name for game in core.collect_games(state)]
            if sorted(dup) != ["AlanWake2", "Control", "DeathStranding"]:
                failures.append(f"duplicate root -> {dup}")
    finally:
        core.scan_steam, core.scan_epic, core.scan_gog, core.scan_ubisoft = original

    if failures:
        for line in failures:
            print("FAIL:", line)
        return 1
    print("PASS: custom root import (7 scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
