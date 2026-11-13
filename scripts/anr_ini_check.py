#!/usr/bin/env python3
"""ANR 参数层回归：nr_fg.ini 的读写、钳制、倍率映射、安装探测。

不碰真实游戏目录：合成树建在仓库 build/ 下（%TEMP% 在 core.DIR_BLACKLIST 里，
虽然这里不经过 core，但保持和其它 check 脚本一致）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import anr_profile as anr  # noqa: E402


def main() -> int:
    failures: list[str] = []
    build = ROOT / "build"
    build.mkdir(exist_ok=True)

    # 1) 默认值
    d = anr.AnrProfile()
    if (d.path, d.max_generated, d.scene_cut, d.nits_per_unit) != ("auto", 5, True, 80):
        failures.append(f"默认值不对: {d}")
    if d.mult != 6:
        failures.append(f"默认倍率应为 6X，得到 {d.mult}")

    # 2) 倍率映射往返
    for mult in range(anr.MULT_MIN, anr.MULT_MAX + 1):
        back = anr.max_generated_to_mult(anr.mult_to_max_generated(mult))
        if back != mult:
            failures.append(f"倍率往返失败: {mult} -> {back}")

    # 3) 预设都指向合法路径
    for name, path in anr.PRESETS.items():
        if path not in anr.PATHS:
            failures.append(f"预设 {name} 指向非法路径 {path}")

    # 4) 容错解析：手改坏的 ini 必须落成可用配置，而不是抛异常
    garbage = (
        "; comment\n"
        "build = user\n"
        "path = nonsense\n"
        "model_size =\n"
        "nits_per_unit = -5\n"
        "max_generated = 99\n"
        "scene_cut = nope\n"
        "unknown_key = 1\n"
    )
    p = anr.AnrProfile.from_ini_text(garbage)
    if p.path != "auto":
        failures.append(f"非法 path 应回退 auto，得到 {p.path}")
    if p.max_generated != 5:
        failures.append(f"max_generated 应钳到 5，得到 {p.max_generated}")
    if p.nits_per_unit != anr.NITS_MIN:
        failures.append(f"nits 应钳到下限 {anr.NITS_MIN}，得到 {p.nits_per_unit}")
    if p.scene_cut is not True:
        failures.append(f"scene_cut 非法值应回退默认 True，得到 {p.scene_cut}")
    if p.model_size != anr.DEFAULT_MODEL_SIZE:
        failures.append(f"空 model_size 应回退默认，得到 {p.model_size!r}")

    # 5) 文本往返
    want = anr.AnrProfile(path="dp4a", max_generated=3, scene_cut=False,
                          nits_per_unit=203, model_size="large")
    got = anr.AnrProfile.from_ini_text(want.to_ini_text())
    if got != want:
        failures.append(f"文本往返不一致: {got} != {want}")

    # 6) 落盘往返 + .bak
    with tempfile.TemporaryDirectory(prefix="anr_ini_", dir=build) as temp:
        ini = Path(temp) / "OptiScaler" / "custom" / "Apex Neural Rendering FG" / "dlssg" / "nr_fg.ini"
        ini.parent.mkdir(parents=True)
        ini.write_text("path = auto\nmax_generated = 5\n", encoding="utf-8")
        anr.save_profile(ini, want)
        if not ini.with_suffix(".ini.bak").exists():
            failures.append("save_profile 没留 .bak")
        if "path = auto" not in ini.with_suffix(".ini.bak").read_text(encoding="utf-8"):
            failures.append(".bak 内容不是旧配置")
        if anr.load_profile(ini) != want:
            failures.append("落盘往返不一致")

        # 7) 缺失文件 → 默认值，不抛异常
        if anr.load_profile(ini.parent / "nope.ini") != anr.AnrProfile():
            failures.append("缺失文件未回退默认值")

        # 8) 安装探测：OptiScaler 布局 / 侧载布局 / 都没有
        game = Path(temp) / "Game"
        game.mkdir()
        if anr.detect_install(game) is not None:
            failures.append("空目录不该探测出 ANR")
        found = anr.detect_install(game)
        if found is not None:
            failures.append(f"空目录误判: {found}")
        (game / anr.INI_RELPATH).parent.mkdir(parents=True)
        (game / anr.INI_RELPATH).write_text("path = auto\n", encoding="utf-8")
        hit = anr.detect_install(game)
        if hit is None or hit.layout != "optiscaler":
            failures.append(f"OptiScaler 布局未识别: {hit}")
        game2 = Path(temp) / "Game2"
        (game2 / anr.SIDELOAD_INI_RELPATH).parent.mkdir(parents=True)
        (game2 / anr.SIDELOAD_INI_RELPATH).write_text("path = auto\n", encoding="utf-8")
        hit2 = anr.detect_install(game2)
        if hit2 is None or hit2.layout != "sideload":
            failures.append(f"侧载布局未识别: {hit2}")

    # 9) 未知键必须保留：ANR 自己还有 nvidia_dlssg 之类的键，重写配置不能弄丢
    with tempfile.TemporaryDirectory(prefix="anr_extra_", dir=build) as temp:
        ini3 = Path(temp) / "nr_fg.ini"
        ini3.write_text("nvidia_dlssg = off\npath = auto\nfoo = bar\n", encoding="utf-8")
        anr.save_profile(ini3, want)
        text = ini3.read_text(encoding="utf-8")
        for needle in ("nvidia_dlssg = off", "foo = bar", "path = dp4a"):
            if needle not in text:
                failures.append(f"未知键/已知键丢失: {needle!r}")
        if anr.parse_extras(text) != {"nvidia_dlssg": "off", "foo": "bar"}:
            failures.append(f"parse_extras 解析不对: {anr.parse_extras(text)}")

    # 10) 布局完整性检查
    with tempfile.TemporaryDirectory(prefix="anr_layout_", dir=build) as temp:
        base = Path(temp) / "dlssg"
        base.mkdir()
        for name in anr.SUPPORT_FILES:
            (base / name).write_text("x", encoding="utf-8")
        for name in anr.SUPPORT_DIRS:
            (base / name).mkdir()
        (base / "nvngx_dlssg.dll").write_bytes(b"MZ")
        if anr.check_layout(base):
            failures.append(f"完整布局被误判: {anr.check_layout(base)}")
        (base / "size_table.json").unlink()
        missing = anr.check_layout(base)
        if "size_table.json" not in missing:
            failures.append(f"缺件未被发现: {missing}")

    if failures:
        for line in failures:
            print("FAIL:", line)
        return 1
    print("PASS: anr profile (10 groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
