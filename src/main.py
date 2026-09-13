"""DLSSG Manager - 程序入口"""
import sys

import i18n
import ui

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

    sys.exit(ui.run(shot, delay))
