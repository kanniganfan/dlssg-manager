#!/usr/bin/env python3
"""检查上游 dlssg_for_sm86 是否有新版本，并验证本地 payload 是否与上游一致。

用途：每次要「看看上游有没有更新」时跑这一条命令即可。

做法（不下载整包）：
  1. 读上游 releases / tags / branches，拿到最新版本号与 main HEAD；
  2. 用 **git blob SHA-1** 对比本地 payload 与上游 HEAD 的每个文件 ——
     这是逐字节一致性的硬证据，比「版本号一样所以应该一样」强。
     blob SHA-1 = sha1(b"blob <len>\\0" + 内容)，GitHub tree API 返回的就是它。

退出码：0 = 已同步；1 = 需要同步（或有文件不一致）。
用法:
    python scripts/check_upstream_sync.py
"""
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import core  # noqa: E402

REPO = "sdli1995/dlssg_for_sm86"
API = f"https://api.github.com/repos/{REPO}"
# 本地 payload 目录（发布目录优先，构建目录兜底）
CANDIDATES = [ROOT.parent / "DLSSG Manager" / "payload", ROOT / "payload"]


def local_payload() -> pathlib.Path:
    for p in CANDIDATES:
        if (p / "version.dll").is_file():
            return p
    raise SystemExit(f"找不到本地 payload，试过：{[str(p) for p in CANDIDATES]}")


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "dlssg-manager-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def git_blob_sha1(path: pathlib.Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def main() -> int:
    payload = local_payload()

    rel = get(f"{API}/releases/latest")
    latest = rel["tag_name"]
    published = rel["published_at"]

    branch = get(f"{API}/branches/main")
    head_sha = branch["commit"]["sha"]
    head_date = branch["commit"]["commit"]["author"]["date"]

    print("=" * 68)
    print("上游同步检查")
    print("=" * 68)
    print(f"  上游最新 Release : {latest}（{published}）")
    print(f"  上游 main HEAD   : {head_sha[:8]}（{head_date}）")
    print(f"  本工具内嵌版本   : {core.MOD_VERSION}（payload {payload}）")
    print()

    # 版本号层面的判断
    newer = core.version_gt(latest, core.MOD_VERSION) if hasattr(core, "version_gt") else None
    if newer:
        print(f"  >> 上游有新版本 {latest} > 内嵌 {core.MOD_VERSION}")
    else:
        print(f"  >> 版本号已追平（内嵌 {core.MOD_VERSION}）")

    # 逐字节层面的判断
    tree = get(f"{API}/git/trees/main?recursive=1")
    remote = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
    ok, bad = 0, []
    for name in sorted(core.PAYLOAD_SHA256):
        local = payload / name
        if name not in remote or not local.is_file():
            bad.append(f"{name}（缺失）")
        elif git_blob_sha1(local) == remote[name]:
            ok += 1
        else:
            bad.append(f"{name}（内容不同）")

    print(f"  >> DLL 一致性    ：{ok}/{len(core.PAYLOAD_SHA256)} 与上游 HEAD 逐字节一致")
    if bad:
        for b in bad:
            print(f"       ! {b}")
    print()

    if newer or bad:
        print("判定：**需要同步** —— 按下面步骤处理")
        print("  1. 下载 https://codeload.github.com/%s/tar.gz/refs/heads/main（约 130 MB，"
              "务必 gzip -t 校验）" % REPO)
        print("  2. 备份 payload 到 _backup_payload_<旧版本>，覆盖 12 个 DLL + 附属文件")
        print("  3. core.py：加一条 PAYLOAD_SHA256_BY_VERSION[新版本]、改 MOD_VERSION")
        print("  4. 同步【安装目录】的 payload（否则 e2e_deploy 会全红）")
        print("  5. 自检 → 打包 → 校验包内哈希 → tag/Release")
        return 1

    print("判定：**已同步**，无需操作")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
