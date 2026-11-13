#!/usr/bin/env python3
"""端到端检查：点「手动添加游戏目录…」→ 自动重扫 → 列表里真的出现这些游戏。

和 import_root_check.py 的区别：那个测 core 的展开逻辑，这个测 UI 那条链路
（add_root → 写 state["roots"] → start_scan → ScanWorker → on_scan_done → 列表）。

离屏运行、不弹窗；LOCALAPPDATA 临时改到仓库 build/ 下，绝不碰真实 state.json。
用法: python scripts/import_flow_check.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)

# 必须在 import core 之前改：core.data_dir() 读的是 LOCALAPPDATA
_SANDBOX = Path(tempfile.mkdtemp(prefix="dlssg_flow_", dir=BUILD))
os.environ["LOCALAPPDATA"] = str(_SANDBOX)

sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

import core  # noqa: E402
import ui  # noqa: E402


def make_exe(path: Path, megabytes: int = 40) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.seek(megabytes * 1024 * 1024 - 1)
        stream.write(b"\0")


def pump(app: QApplication, predicate, timeout: float) -> bool:
    """转事件循环直到 predicate 为真或超时。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    app.processEvents()
    return bool(predicate())


def main() -> int:
    app = QApplication.instance() or QApplication([])

    # 隔离：不要把本机真实 Steam/Epic 库混进来
    core.scan_steam = core.scan_epic = core.scan_gog = core.scan_ubisoft = lambda: []

    lib = _SANDBOX / "MyGames"
    make_exe(lib / "setup.exe", 6)                       # 库根上的安装器（旧代码就是被它骗到）
    for name in ("Hades", "Celeste", "Hollow"):
        make_exe(lib / "Steam" / name / "Binaries" / "Win64" / f"{name}-Win64-Shipping.exe")

    # 「手动添加游戏目录…」直接返回我们的库路径
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(lib))

    win = ui.MainWindow()
    # 首启的后台线程（显卡探测 / 运行包校验）先跑完，别和扫描抢
    pump(app, lambda: not (getattr(win, "worker", None) and win.worker.isRunning()), 60)

    fails: list[str] = []

    # ---- 真实槽函数 ----
    win.add_root()

    ok = pump(app, lambda: (not win.worker.isRunning()) and len(win.games) > 0, 180)
    if not ok:
        fails.append(f"扫描没有结果（games={len(win.games)}，worker_running={win.worker.isRunning()}）")

    got = sorted(g.name for g in win.games)
    if got != ["Celeste", "Hades", "Hollow"]:
        fails.append(f"列表内容不对: {got}")

    if sorted(win.cards) != sorted(g.gid for g in win.games):
        fails.append(f"卡片数({len(win.cards)})与游戏数({len(win.games)})不一致")

    state = core.load_state()
    if state.get("roots") != [str(lib)]:
        fails.append(f"state[\"roots\"] 没写对: {state.get('roots')}")

    # 再点一次同一个目录：不能出重复
    win.add_root()
    pump(app, lambda: not win.worker.isRunning(), 180)
    if sorted(g.name for g in win.games) != ["Celeste", "Hades", "Hollow"]:
        fails.append(f"重复添加后变多了: {sorted(g.name for g in win.games)}")
    if core.load_state().get("roots") != [str(lib)]:
        fails.append(f"重复添加把 roots 写重了: {core.load_state().get('roots')}")

    # 等开屏动画（Splash）撤掉再截图，否则抓到的是加载页
    pump(app, lambda: getattr(win, "splash", None) is None, 20)
    win.resize(1280, 900)
    pump(app, lambda: False, 0.5)
    shot = BUILD / "_shot_import_flow.png"
    win.grab().save(str(shot))

    if fails:
        for line in fails:
            print("FAIL:", line)
        return 1
    print(f"PASS: add_root -> scan -> list ({len(win.games)} games); "
          f"roots={core.load_state().get('roots')}; shot={shot.name}")
    return 0


if __name__ == "__main__":
    # PySide6 + offscreen 在解释器退出阶段偶尔会炸（0xC0000409），
    # 断言已经跑完了，所以刷出缓冲后直接 _exit，别让 Qt 的析构把结果带崩。
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
