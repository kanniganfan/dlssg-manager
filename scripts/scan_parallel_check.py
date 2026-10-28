#!/usr/bin/env python3
"""Synthetic regression and timing check for the bounded game-root scan pool."""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import core  # noqa: E402


def projection(games):
    return [(g.gid, g.name, g.exe, g.exe_dir, g.source, g.engine, g.dlssg, g.dlss,
             g.anticheat, g.entry, g.deployed, g.resolution,
             tuple((c["exe"], c["score"], c["dlssg"], c["dlss"]) for c in g.candidates))
            for g in games]


def main() -> int:
    build_dir = Path(__file__).resolve().parent.parent / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dlssg_scan_parallel_", dir=build_dir) as temp:
        base = Path(temp)
        roots: list[tuple[str, str, str]] = []
        for i in range(16):
            root = base / f"Game{i:02d}"
            exe_dir = root / "Binaries" / "Win64"
            exe_dir.mkdir(parents=True)
            (exe_dir / f"Game{i:02d}-Win64-Shipping.exe").write_bytes(b"MZ\0\0")
            (exe_dir / "nvngx_dlssg.dll").write_bytes(b"synthetic")
            roots.append((root.name, str(root), "Synthetic"))
        # The duplicate path must still collapse to its first source.
        roots.append(("Duplicate", str(base / "Game00"), "Duplicate"))

        original_scanners = (core.scan_steam, core.scan_epic, core.scan_gog, core.scan_ubisoft)
        original_find = core.find_candidates
        original_guess = core.guess_resolution
        original_limit = core.SCAN_MAX_WORKERS
        lock = threading.Lock()
        active = 0
        max_active = 0

        def delayed_find(path):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.04)
                return original_find(path)
            finally:
                with lock:
                    active -= 1

        try:
            core.scan_steam = core.scan_epic = core.scan_gog = core.scan_ubisoft = lambda: []
            core.find_candidates = delayed_find
            core.guess_resolution = lambda *_args: (1920, 1080)
            state = {"games": {}, "roots": []}

            core.SCAN_MAX_WORKERS = 1
            started = time.perf_counter()
            serial = core.collect_games(state, extra=roots)
            serial_seconds = time.perf_counter() - started
            serial_projection = projection(serial)

            max_active = 0
            core.SCAN_MAX_WORKERS = 4
            started = time.perf_counter()
            parallel = core.collect_games(state, extra=roots)
            parallel_seconds = time.perf_counter() - started

            if projection(parallel) != serial_projection:
                raise AssertionError("parallel scan changed game data or result ordering")
            if len(parallel) != 16:
                raise AssertionError(f"expected 16 unique synthetic games, got {len(parallel)}")
            if not 2 <= max_active <= 4:
                raise AssertionError(f"expected bounded parallelism 2–4, observed {max_active}")
            if parallel_seconds >= serial_seconds * 0.8:
                raise AssertionError(
                    f"parallel scan was not materially faster in synthetic test: "
                    f"serial={serial_seconds:.3f}s parallel={parallel_seconds:.3f}s"
                )
            ignored_game = parallel[0]
            core.ignore_game(state, ignored_game)
            ignored_results = core.collect_games(state, extra=roots)
            if len(ignored_results) != 15 or any(g.gid == ignored_game.gid for g in ignored_results):
                raise AssertionError("an ignored game reappeared in subsequent scan results")
            if core.unignore_game(state, ignored_game.gid) is None:
                raise AssertionError("ignored game could not be restored")
            restored_results = core.collect_games(state, extra=roots)
            if projection(restored_results) != serial_projection:
                raise AssertionError("restoring an ignored game did not reproduce the original results")
            print(f"PASS: {len(parallel)} deterministic games; max active={max_active}; "
                  f"serial={serial_seconds:.3f}s parallel={parallel_seconds:.3f}s; ignore/restore=PASS")
            return 0
        finally:
            core.scan_steam, core.scan_epic, core.scan_gog, core.scan_ubisoft = original_scanners
            core.find_candidates = original_find
            core.guess_resolution = original_guess
            core.SCAN_MAX_WORKERS = original_limit


if __name__ == "__main__":
    raise SystemExit(main())
