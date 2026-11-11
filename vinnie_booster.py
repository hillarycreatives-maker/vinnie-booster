#!/usr/bin/env python3
"""Safe Windows storage scanner.

Report-only by design: this script never deletes, moves, or modifies files.
Run from Command Prompt or PowerShell with Python 3.10+.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable


DEFAULT_TOP = 50
DEFAULT_MAX_DEPTH = 12


def print_ram_status() -> int:
    """Print read-only Windows memory status; never terminates processes."""
    print("=== VINNIE BOOSTER :: RAM CHECK ===")
    if os.name != "nt":
        print("RAM check is available when this script is run on Windows.")
        return 0
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        print("Windows could not provide memory status.")
        return 1
    to_gb = 1024 ** 3
    print(f"Memory load: {status.dwMemoryLoad}%")
    print(f"Available:   {status.ullAvailPhys / to_gb:.1f} GB")
    print(f"Total:       {status.ullTotalPhys / to_gb:.1f} GB")
    if status.dwMemoryLoad >= 90:
        print("Recommendation: close unused applications and browser tabs, then check Task Manager.")
    elif status.dwMemoryLoad >= 75:
        print("Recommendation: review heavy applications in Task Manager before starting more work.")
    else:
        print("Recommendation: memory pressure is currently moderate.")
    print("Vinnie Booster does not terminate processes or claim to create RAM.")
    return 0

# These locations are protected or require review even if they are large.
PROTECTED_NAMES = {
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "$Recycle.Bin",
    "System Volume Information",
    "Recovery",
}

REVIEW_NAME_HINTS = {
    "downloads": "Downloads folder: review personal files and installers",
    "temp": "Temporary files: usually removable, but review first",
    "cache": "Cache: often removable, but applications may rebuild it",
    "crashdumps": "Crash dumps: usually removable after review",
    "thumbcache": "Thumbnail cache: usually removable",
}

REVIEW_EXTENSIONS = {
    ".iso": "Disk image: remove only if no longer needed",
    ".zip": "Archive: review contents and backups before removing",
    ".7z": "Archive: review contents and backups before removing",
    ".rar": "Archive: review contents and backups before removing",
    ".msi": "Installer: may be needed for repair/uninstall",
    ".exe": "Executable/installer: review before removing",
    ".dmg": "Disk image: review before removing",
    ".bak": "Backup file: verify a newer backup exists",
    ".old": "Old-version file: verify it is not needed",
    ".vhd": "Virtual disk: do not remove without checking its owner",
    ".vhdx": "Virtual disk: do not remove without checking its owner",
    ".pst": "Mail archive: personal data, review carefully",
    ".ost": "Outlook data: do not remove unless Outlook guidance says so",
    ".db": "Database: do not remove without identifying the application",
    ".sqlite": "Database: do not remove without identifying the application",
}


def human_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def normalize(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def classify(path: Path, is_dir: bool, protected_roots: list[str]) -> tuple[str, str]:
    normalized = normalize(path)
    if any(normalized == root or normalized.startswith(root + os.sep) for root in protected_roots):
        return "protected", "System or application location"

    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & {name.lower() for name in PROTECTED_NAMES}:
        return "protected", "System or application location"

    if is_dir:
        for part in reversed(path.parts):
            hint = REVIEW_NAME_HINTS.get(part.lower())
            if hint:
                return "review", hint
        return "review", "Folder contents require review"

    hint = REVIEW_EXTENSIONS.get(path.suffix.lower())
    if hint:
        return "review", hint
    for part in path.parts:
        hint = REVIEW_NAME_HINTS.get(part.lower())
        if hint:
            return "review", hint
    return "review", "Large file; confirm it is not needed"


def safe_roots() -> list[Path]:
    roots: list[Path] = []
    for env_name in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))
    return roots


def iter_entries(root: Path, max_depth: int) -> Iterable[tuple[Path, bool, int, str | None]]:
    """Yield files and folders with best-effort size information."""
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as entries:
                children = list(entries)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            yield current, True, 0, "inaccessible"
            continue

        total = 0
        for entry in children:
            try:
                entry_path = Path(entry.path)
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    total += size
                    yield entry_path, False, size, None
                elif entry.is_dir(follow_symlinks=False):
                    if depth < max_depth:
                        stack.append((entry_path, depth + 1))
            except (PermissionError, FileNotFoundError, OSError):
                continue
        yield current, True, total, None


def scan(root: Path, max_depth: int, protected_roots: list[str]) -> tuple[list[dict], dict]:
    records: list[dict] = []
    folder_sizes: defaultdict[str, int] = defaultdict(int)
    scanned_files = 0
    scanned_dirs = 0
    inaccessible = 0

    for path, is_dir, size, error in iter_entries(root, max_depth):
        if error:
            inaccessible += 1
        if is_dir:
            scanned_dirs += 1
        else:
            scanned_files += 1
            # Add each file to all existing ancestors in this scan's root.
            parent = path.parent
            while True:
                folder_sizes[normalize(parent)] += size
                if normalize(parent) == normalize(root) or parent == parent.parent:
                    break
                parent = parent.parent

        category, reason = classify(path, is_dir, protected_roots)
        records.append({
            "path": str(path),
            "type": "folder" if is_dir else "file",
            "size_bytes": size,
            "size": human_bytes(size),
            "category": category,
            "reason": reason,
            "extension": path.suffix.lower() if not is_dir else "",
        })

    for path_text, size in folder_sizes.items():
        path = Path(path_text)
        category, reason = classify(path, True, protected_roots)
        records.append({
            "path": str(path),
            "type": "folder_total",
            "size_bytes": size,
            "size": human_bytes(size),
            "category": category,
            "reason": reason,
            "extension": "",
        })

    records.sort(key=lambda item: item["size_bytes"], reverse=True)
    stats = {
        "scanned_files": scanned_files,
        "scanned_directories": scanned_dirs,
        "inaccessible_entries": inaccessible,
    }
    return records, stats


def write_reports(output_dir: Path, records: list[dict], stats: dict, roots: list[Path], elapsed: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"storage_scan_{timestamp}.json"
    csv_path = output_dir / f"storage_scan_{timestamp}.csv"
    txt_path = output_dir / f"storage_scan_{timestamp}.txt"

    payload = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "roots": [str(root) for root in roots],
        "elapsed_seconds": round(elapsed, 2),
        "stats": stats,
        "records": records,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "type", "size_bytes", "size", "category", "reason", "extension"])
        writer.writeheader()
        writer.writerows(records)

    top = records[:DEFAULT_TOP]
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("SAFE STORAGE SCAN — REPORT ONLY\n")
        handle.write("No files were deleted or modified.\n\n")
        handle.write(f"Roots: {', '.join(str(root) for root in roots)}\n")
        handle.write(f"Elapsed: {elapsed:.1f} seconds\n")
        handle.write(f"Files: {stats['scanned_files']:,}; directories: {stats['scanned_directories']:,}; inaccessible: {stats['inaccessible_entries']:,}\n\n")
        handle.write("Largest items (folders may include the sizes of their child files):\n")
        for number, item in enumerate(top, 1):
            handle.write(f"{number:>3}. [{item['category'].upper():9}] {item['size']:>10}  {item['path']}\n")
            handle.write(f"     {item['reason']}\n")
        handle.write("\nCategories:\n")
        handle.write("  PROTECTED = system/application location; do not remove based on this report.\n")
        handle.write("  REVIEW    = possible cleanup candidate, but requires your confirmation.\n")

    print(f"\nReports written to: {output_dir}")
    print(f"  Text summary: {txt_path}")
    print(f"  Spreadsheet-friendly CSV: {csv_path}")
    print(f"  Full JSON: {json_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely scan Windows storage without deleting anything.")
    parser.add_argument("root", nargs="?", default="C:\\", help="Drive or folder to scan, default: C:\\")
    parser.add_argument("--output", default="storage_scan_reports", help="Folder for reports")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help=f"Maximum folder depth, default: {DEFAULT_MAX_DEPTH}")
    parser.add_argument("--ram", action="store_true", help="Show read-only RAM status and safe recommendations")
    args = parser.parse_args()

    if args.ram:
        return print_ram_status()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: scan root does not exist or is not a folder: {root}", file=sys.stderr)
        return 2
    if args.max_depth < 1:
        print("Error: --max-depth must be at least 1", file=sys.stderr)
        return 2

    protected_roots = [normalize(path) for path in safe_roots()]
    print("=== VINNIE BOOSTER :: STORAGE SCAN ===")
    print(f"Scanning: {root}")
    print("Report-only mode: no files will be deleted or modified.")
    print("This may take time on a large drive; progress is shown when complete.")
    started = time.monotonic()
    records, stats = scan(root, args.max_depth, protected_roots)
    elapsed = time.monotonic() - started
    write_reports(Path(args.output), records, stats, [root], elapsed)
    print(f"Scanned {stats['scanned_files']:,} files and {stats['scanned_directories']:,} directories in {elapsed:.1f} seconds.")
    print("Open the TXT summary first. Do not delete protected items; review candidates manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
