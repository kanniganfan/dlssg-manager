#!/usr/bin/env python3
"""端到端部署 / 恢复闭环测试（在临时目录里做，不碰任何真实游戏）。

验证：部署写出正确的 DLL + INI → 读回配置 → 恢复后目录干净。
用法: python scripts/e2e_deploy.py
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import core  # noqa: E402


def main() -> int:
    fails: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="dlssg_e2e_"))
    print(f"临时游戏目录: {tmp}")
    # Keep the test's state and rollback copies inside its disposable directory.
    state_root = tmp / "test-app-state"
    core.data_dir = lambda: state_root
    core.state_file = lambda: state_root / "state.json"

    log_file = tmp / "dlssg_sm86" / "logs" / "keep-me.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text("user log", encoding="utf-8")
    custom_backend = tmp / "dlssg_sm86" / "backend" / "sm86_backend.dll"
    custom_backend.parent.mkdir(parents=True)
    custom_backend.write_bytes(b"pre-existing user file")

    try:
        # 造一个假的渲染 EXE，让 deploy 的“游戏运行中”检查走空路径
        fake_exe = tmp / "FakeGame.exe"
        fake_exe.write_bytes(b"MZ" + b"\0" * 62)
        g = core.Game(name="E2E", exe_dir=str(tmp), exe=str(fake_exe),
                      source="Steam", resolution=(1920, 1080), dlssg=True)

        cases = [
            ("DLSS", 4, 1, "A", "Off"),
            ("DLSS", 6, 3, "C", "Off"),
            ("XeSS", 4, 1, "A", "Off"),
            ("DLSS", 4, 2, "B", "M-INT8"),
        ]
        for engine, mult, tier, preset, sr_mode in cases:
            print(f"\n=== 部署 engine={engine} mult={mult} tier={tier} ===")
            ok, logs = core.deploy(g, "SM86", mult, False, 1, "", False,
                                   core.DEFAULT_RUNTIME, tier, engine=engine,
                                   preset=preset, sr_mode=sr_mode)
            if not ok:
                fails.append(f"{engine}/{mult}/{tier} 部署失败: {logs}")
                for l in logs:
                    print("   ", l)
                continue

            # 1) 入口 DLL 必须存在且哈希与 payload 一致
            entry = [e for e in core.ENTRIES if (tmp / e[1]).is_file()]
            if not entry:
                fails.append(f"{engine}: 未写出任何入口 DLL")
                continue
            fname = entry[0][1]
            src = core.payload_for_entry(fname, core.DEFAULT_RUNTIME)[0]
            got = hashlib.sha256((tmp / fname).read_bytes()).hexdigest()
            want = hashlib.sha256(src.read_bytes()).hexdigest()
            dll_ok = got == want
            print(f"    DLL {fname}: {'哈希一致' if dll_ok else '哈希不符'}")
            if not dll_ok:
                fails.append(f"{engine}: {fname} 哈希不符")
            for rel in core.GAME_SUPPORT_FILES:
                deployed = tmp / rel
                if not deployed.is_file() or hashlib.sha256(deployed.read_bytes()).hexdigest() != core.PAYLOAD_SHA256[rel]:
                    fails.append(f"{engine}: 运行文件 {rel} 缺失或哈希不符")

            # 2) INI 的 Optimized 必须是钳制后的档位
            cfg = core.read_deployed_config(str(tmp))
            expect_tier = min(tier, core.tier_cap(core.DEFAULT_RUNTIME))
            got_tier = cfg.get("tier")
            ini_ok = got_tier == expect_tier
            print(f"    INI: Optimized={cfg.get('Optimized')} tier={got_tier} "
                  f"(期望 {expect_tier})  MaxGeneratedFrames={cfg.get('MaxGeneratedFrames')}"
                  f"  {'OK' if ini_ok else 'FAIL'}")
            if not ini_ok:
                fails.append(f"{engine}/{tier}: INI 档位 {got_tier} != {expect_tier}")
            if cfg.get("Engine") != engine or cfg.get("Preset") != preset or cfg.get("SRMode") != sr_mode:
                fails.append(f"{engine}: Engine/Preset/SRMode 配置写回错误: {cfg}")
            # 倍率也要落在 INI 里
            exp_mult = min(mult, core.runtime_mult_cap(core.DEFAULT_RUNTIME, engine))
            if cfg.get("MaxGeneratedFrames") != str(exp_mult - 1):
                fails.append(f"{engine}: MaxGeneratedFrames="
                             f"{cfg.get('MaxGeneratedFrames')} != {exp_mult - 1}")

            # 3) 识别为「本项目的部署」
            de, ours = core.entry_of_deployment(str(tmp))
            print(f"    识别部署: entry={de} is_ours={ours}")
            if not ours:
                fails.append(f"{engine}: 未能识别为本项目部署")

            # 4) 恢复 → 目录应干净
            ok2, logs2 = core.restore(g)
            left = [e[1] for e in core.ENTRIES if (tmp / e[1]).is_file()]
            ini_left = (tmp / core.INI_NAME).is_file()
            remaining_payload = [rel for rel in core.GAME_SUPPORT_FILES
                                 if rel != "dlssg_sm86/backend/sm86_backend.dll" and (tmp / rel).is_file()]
            print(f"    恢复: ok={ok2} 残留DLL={left} 运行文件={remaining_payload} INI={ini_left}")
            if not ok2 or left or remaining_payload or ini_left:
                fails.append(f"{engine}: 恢复未完成 DLL={left} payload={remaining_payload} INI={ini_left}")
            if not custom_backend.is_file() or custom_backend.read_bytes() != b"pre-existing user file":
                fails.append(f"{engine}: 恢复未还原同名用户文件")
            if not log_file.is_file() or log_file.read_text(encoding="utf-8") != "user log":
                fails.append(f"{engine}: 用户日志受影响")

        print("\n=== 结果 ===")
        if fails:
            for f in fails:
                print("  FAIL:", f)
            print(f"合计 {len(fails)} 项失败")
            return 1
        print("  全部断言通过")

        # 顺带确认真实 payload 校验无警告
        w = core.verify_payload()
        print(f"\nverify_payload: {'全部通过' if not w else w}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"已清理 {tmp}")


if __name__ == "__main__":
    sys.exit(main())
