#!/usr/bin/env python3
"""ANR 部署层回归：官方数据表推荐 + 平铺部署/还原。

全部在 build/ 沙箱里跑，绝不碰真实游戏目录。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import anr_deploy  # noqa: E402
import anr_profile as anr  # noqa: E402

BUILD = ROOT / "build"


def main() -> int:
    fails: list[str] = []
    source = anr_deploy.default_source_dir(ROOT)
    if source is None:
        print("SKIP: 没有可用的 ANR 源目录（先跑 scripts/anr_layout_probe.py）")
        return 2

    # 1) 显卡名 → 架构
    cases = {
        "NVIDIA GeForce RTX 3050 Laptop GPU": ("nvidia", "ampere"),
        "NVIDIA GeForce RTX 2080 Ti": ("nvidia", "turing"),
        "NVIDIA GeForce RTX 4070": ("nvidia", "ada"),
        "NVIDIA GeForce RTX 5090": ("nvidia", "blackwell"),
        "AMD Radeon RX 6800 XT": ("amd", "rdna2"),
        "AMD Radeon RX 7900 XTX": ("amd", "rdna3"),
    }
    for name, want in cases.items():
        got = anr.gpu_arch(name)
        if got != want:
            fails.append(f"架构映射错: {name} -> {got}（应 {want}）")
    if anr.gpu_arch("Intel Arc B580") is not None:
        fails.append("Intel 不该映射到 nvidia/amd 架构")

    # 2) 分辨率档
    if anr.size_class(1920, 1080) != "1080p":
        fails.append("1920x1080 应为 1080p")
    if anr.size_class(2560, 1440) != "1440p":
        fails.append("2560x1440 应为 1440p")
    if anr.size_class(3840, 2160) != "2160p":
        fails.append("3840x2160 应为 2160p")

    # 3) 官方表推荐
    rec = anr.recommend(source, "NVIDIA GeForce RTX 3050 Laptop GPU", 1920, 1080)
    if rec is None:
        fails.append("RTX 3050 @1080p 没有推荐结果")
    else:
        if rec.architecture != "ampere" or rec.path != "coopmat":
            fails.append(f"推荐内容不对: {rec}")
        if (rec.mult_min, rec.mult_max) != (2, 6):
            fails.append(f"倍率区间不对: {rec.mult_min}-{rec.mult_max}")

    # turing 在 4K 只有 2X —— 这条能验证「按分辨率取区间」真的生效
    turing_4k = anr.recommend(source, "NVIDIA GeForce RTX 2080 Ti", 3840, 2160)
    if turing_4k is None:
        fails.append("RTX 2080 Ti @4K 没有推荐结果")
    elif (turing_4k.mult_min, turing_4k.mult_max) != (2, 2):
        fails.append(f"turing 4K 应为 2X 上限，得到 {turing_4k.mult_min}-{turing_4k.mult_max}")

    # 4) 平铺部署 / 还原
    with tempfile.TemporaryDirectory(prefix="anr_deploy_", dir=BUILD) as temp:
        game = Path(temp) / "Game"
        game.mkdir()
        own_dll = game / "nvngx_dlssg.dll"
        own_dll.write_bytes(b"GAME-ORIGINAL-DLL")
        (game / "game.exe").write_bytes(b"MZ")
        before = sorted(p.relative_to(game).as_posix() for p in game.rglob("*"))

        record = anr_deploy.deploy(game, source, Path(temp) / "backups")
        written = sorted(item["path"] for item in record["files"])
        if "nvngx_dlssg.dll" not in written or "programs/fg-lite-any-coopmat-pq10/pack.nrx" not in written:
            fails.append(f"部署文件清单不对: {written[:5]}...")
        if len(written) < 19:
            fails.append(f"部署文件太少: {len(written)}")
        if "nvngx_dlssg.dll" not in record["backups"]:
            fails.append("覆盖游戏自带 DLL 前没有备份")
        if own_dll.read_bytes() == b"GAME-ORIGINAL-DLL":
            fails.append("部署后游戏自带 DLL 没被覆盖（说明没真正写入）")

        # 改动一个文件后再还原：那个文件应被保留（不当“我们的”删掉）
        touched = game / "nr_fg.ini"
        touched.write_text("path = auto\n; hand edited\n", encoding="utf-8")

        log = anr_deploy.restore(game, record)
        if not own_dll.exists() or own_dll.read_bytes() != b"GAME-ORIGINAL-DLL":
            fails.append("还原后游戏自带 DLL 没回来")
        if not touched.exists():
            fails.append("被手工改过的 nr_fg.ini 应保留，但被删了")
        if (game / "programs").exists():
            fails.append("还原后 programs/ 目录没清理")
        after = sorted(p.relative_to(game).as_posix() for p in game.rglob("*"))
        if after != sorted(before + ["nr_fg.ini"]):
            fails.append(f"还原后目录不干净: {after}")
        if not any("跳过（已被改动）" in line for line in log):
            fails.append("日志里应提示跳过被改动的文件")

    if fails:
        for line in fails:
            print("FAIL:", line)
        return 1
    print("PASS: anr deploy (recommend + flat deploy/restore)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
