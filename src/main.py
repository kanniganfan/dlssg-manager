"""DLSSG Manager - 程序入口"""
import ctypes
import os
import sys
from pathlib import Path

import i18n
import ui


def _elevate() -> None:
    """默认以管理员身份运行。

    需要管理员的三个功能：HAGS 开关（写 HKLM）、显卡设备重启、以及往
    Program Files 下的游戏目录写文件。非管理员时用 UAC 重新拉起自己，
    本进程立刻退出（避免出现两个实例）。
    设置 DLSSG_NO_ELEVATE=1 可以跳过，方便自动化测试。
    """
    if os.name != "nt" or os.environ.get("DLSSG_NO_ELEVATE"):
        return
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
        # 提权后的进程工作目录会变成 System32，所以脚本路径和 cwd 都要给绝对路径，
        # 否则新进程起来后立刻因为找不到 main.py 退出（表现为「点了没反应」）。
        if getattr(sys, "frozen", False):
            args = list(sys.argv[1:])
        else:
            args = [str(Path(sys.argv[0]).resolve())] + list(sys.argv[1:])
        params = " ".join(f'"{a}"' for a in args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, str(Path.cwd()), 1)
        if rc > 32:                 # >32 = 成功（UAC 已同意，新进程已启动）
            sys.exit(0)
        print(f"[警告] 无法获取管理员权限（ShellExecuteW={rc}），以普通权限继续")
    except Exception as exc:        # 没有 UAC / 被拒绝时不要崩，降级运行
        print(f"[警告] 提权失败：{exc}，以普通权限继续")


if __name__ == "__main__":
    args = sys.argv[1:]
    shot = args[args.index("--shot") + 1] if "--shot" in args else ""
    delay = int(args[args.index("--shot-delay") + 1]) if "--shot-delay" in args else 12000

    # 语言优先级：--lang 命令行  >  state.json 里保存的  >  系统语言（i18n 导入时已设）
    lang = ""
    if "--lang" in args:
        lang = args[args.index("--lang") + 1]
    if not lang:
        try:
            lang = ui.core.load_state().get("lang", "")
        except Exception:
            lang = ""
    if lang:
        i18n.set_lang(lang)

    if not shot:                    # 截图模式（自动化测试）不弹 UAC
        _elevate()

    sys.exit(ui.run(shot, delay))
