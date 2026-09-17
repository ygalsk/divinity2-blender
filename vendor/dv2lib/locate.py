"""Where the game is on this machine."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

FOLDER = "divinity2_dev_cut"                     # Steam's folder under steamapps/common
PROCESS_NAMES = ("Divinity2-debug.exe", "Divinity2.exe")
VDF_PATH = re.compile(r'"path"\s*"([^"]+)"')


def packed(game: Path) -> Path:
    return Path(game) / "Data" / "Win32" / "Packed"


def is_game(path: Path | str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return packed(p).is_dir() and any((p / "bin" / n).exists() for n in PROCESS_NAMES)


def packed_of(path: Path | str) -> Path | None:
    """The folder of archives, given the game folder or that folder itself."""
    for p in (packed(Path(path)), Path(path)):
        if p.is_dir() and any(p.glob("*.dv2")):
            return p
    return None


def steam_roots() -> list[Path]:
    """Every place a Steam install can be on this platform, existing or not."""
    home = Path.home()
    if sys.platform == "win32":
        roots = []
        try:
            import winreg
            for hive, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                     (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        roots.append(Path(winreg.QueryValueEx(k, value)[0]))
                except OSError:
                    pass
        except ImportError:
            pass
        pf = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles") or r"C:\Program Files (x86)"
        return roots + [Path(pf) / "Steam"]
    if sys.platform == "darwin":
        return [home / "Library/Application Support/Steam"]
    return [home / ".steam/steam", home / ".local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            home / "snap/steam/common/.local/share/Steam"]


def steam_libraries() -> list[Path]:
    """Every `steamapps` directory Steam knows, the roots first."""
    seen: list[Path] = []
    for root in steam_roots():
        apps = root / "steamapps"
        candidates = [apps]
        vdf = apps / "libraryfolders.vdf"
        if vdf.exists():
            text = vdf.read_text(errors="replace").replace("\\\\", "\\")
            candidates += [Path(m) / "steamapps" for m in VDF_PATH.findall(text)]
        for c in candidates:
            try:
                r = c.resolve()
            except OSError:
                continue
            if r.is_dir() and r not in seen:
                seen.append(r)
    return seen


def find_game() -> Path | None:
    """`DV2_GAME` when set, else the Developer's Cut in any Steam library."""
    env = os.environ.get("DV2_GAME")
    if env:
        return Path(env) if is_game(env) else None
    for apps in steam_libraries():
        g = apps / "common" / FOLDER
        if is_game(g):
            return g
    return None
