#!/usr/bin/env python3
"""Import the pinned DLSSG upstream release into the local build payload.

The release archive is verified before extraction. Archive members are checked
for path traversal, links, duplicate names, and unreasonable expansion sizes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.4.1"
ARCHIVE_SHA256 = "7230131637617ede9dc45c552244ddb814ae70098406e102fc254d52bcdb6e14"
MAX_UNCOMPRESSED = 350 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_member_name(info: zipfile.ZipInfo, seen: set[str]) -> PurePosixPath | None:
    name = info.filename
    if "\\" in name or any(ord(ch) < 32 for ch in name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    path = PurePosixPath(name)
    windows = PureWindowsPath(name)
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if path.is_absolute() or windows.drive or ".." in parts or not parts:
        raise ValueError(f"Unsafe archive path: {name!r}")
    key = "/".join(parts).casefold()
    if key in seen:
        raise ValueError(f"Duplicate archive path: {name!r}")
    seen.add(key)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValueError(f"Links are not allowed in the release archive: {name!r}")
    if not (info.is_dir() or mode == 0 or stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise ValueError(f"Unsupported archive member type: {name!r}")
    return None if info.is_dir() else PurePosixPath(*parts)


def import_release(archive: Path, force: bool = False) -> None:
    if not archive.is_file():
        raise FileNotFoundError(archive)
    actual_archive_hash = sha256_file(archive)
    if actual_archive_hash != ARCHIVE_SHA256:
        raise ValueError(f"Archive SHA-256 mismatch: {actual_archive_hash}")

    payload = ROOT / "payload"
    manifest_module = ROOT / "src" / "upstream_payload.py"
    # payload/ 是派生产物：已存在就默认拒绝，除非显式 --force（旧的会留成 .bak）。
    if payload.exists() and not force:
        raise FileExistsError(
            "payload/ 已存在；如要重建请加 --force（旧目录会改名成 payload.bak-<时间> 保留）")
    # src/upstream_payload.py 是上游内容的「钉子」：已存在时**不覆盖**，
    # 而是要求这次解出来的清单与它逐字节一致 —— 不一致说明上游内容变了，直接失败。
    pinned_text = manifest_module.read_text(encoding="utf-8") if manifest_module.exists() else None

    stage = Path(tempfile.mkdtemp(prefix=".payload-0.4.1-", dir=ROOT))
    module_tmp: Path | None = None
    try:
        files: dict[str, str] = {}
        seen: set[str] = set()
        with zipfile.ZipFile(archive) as zf:
            if sum(info.file_size for info in zf.infolist()) > MAX_UNCOMPRESSED:
                raise ValueError("Release archive exceeds the allowed expanded size")
            bad = zf.testzip()
            if bad:
                raise ValueError(f"Corrupt archive member: {bad}")
            members = [(info, safe_member_name(info, seen)) for info in zf.infolist()]
            for info, rel in members:
                if rel is None:
                    continue
                target = stage.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                written = 0
                with zf.open(info, "r") as source, target.open("xb") as sink:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        sink.write(block)
                        h.update(block)
                        written += len(block)
                if written != info.file_size:
                    raise ValueError(f"Length mismatch after extraction: {info.filename}")
                files[rel.as_posix()] = h.hexdigest()

        data = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        module_text = (
            '"""Generated from the hash-verified upstream DLSSG release. Do not edit."""\n'
            f"UPSTREAM_VERSION = {VERSION!r}\n"
            f"UPSTREAM_ARCHIVE_SHA256 = {ARCHIVE_SHA256!r}\n"
            f"PAYLOAD_FILES_SHA256 = __import__('json').loads({data!r})\n"
        )
        if pinned_text is not None and pinned_text != module_text:
            raise ValueError(
                "解出的文件清单与 src/upstream_payload.py 里的钉子不一致："
                "上游包内容或 VERSION / ARCHIVE_SHA256 被改过，请先核对再导入")

        fd, tmp_name = tempfile.mkstemp(prefix="upstream_payload.", suffix=".tmp", dir=manifest_module.parent)
        os.close(fd)
        module_tmp = Path(tmp_name)
        module_tmp.write_text(module_text, encoding="utf-8", newline="\n")

        backup: Path | None = None
        if payload.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = payload.with_name(f"payload.bak-{stamp}")
            os.replace(payload, backup)
        os.replace(stage, payload)
        try:
            if pinned_text is None:      # 首次导入才写钉子
                os.replace(module_tmp, manifest_module)
        except Exception:
            os.replace(payload, stage)
            if backup is not None:
                os.replace(backup, payload)
            raise
        kept = "（清单与钉子一致，未改动 src/upstream_payload.py）" if pinned_text is not None else ""
        print(f"Imported upstream {VERSION}: {len(files)} files, "
              f"archive SHA-256 {actual_archive_hash}{kept}")
        if backup is not None:
            print(f"旧 payload 已保留为 {backup.name}")
    finally:
        if module_tmp and module_tmp.exists():
            module_tmp.unlink()
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="official dlssg-release-0.4.1-x64.zip")
    parser.add_argument("--force", action="store_true",
                        help="payload/ 已存在时重建（旧的改名成 payload.bak-<时间>）")
    args = parser.parse_args()
    import_release(args.archive.resolve(), force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
